#!/usr/bin/env python3
"""
training/train_dpo.py
─────────────────────
Multi-Agent DPO training pipeline.
Trains 3 specialized LoRA adapters (RAG, Quiz, Feedback) sequentially 
ONLY if they meet the 50-pair threshold. Merges into a Master Specialist.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import subprocess
from pathlib import Path

try:
    import unsloth
except ImportError:
    print("Unsloth not found. Installing dependencies for Kaggle environment...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "unsloth", "trl", "peft", "accelerate", "bitsandbytes", "datasets"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dpo_train")


DEFAULT_MODEL = "unsloth/gemma-3-4b-it-bnb-4bit"
DEFAULT_DATASET = "dpo_dataset.jsonl"
DEFAULT_OUTPUT = "output/eduverse-gemma4-dpo"
MIN_PAIRS_PER_AGENT = 200
MAX_SEQ_LENGTH = 2048


def load_and_filter_data(path: str):
    """Loads JSONL and groups by agent type."""
    from datasets import Dataset

    agent_data = {"rag_tutor": [], "quiz_drafter": [], "feedback_mentor": []}
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            row = json.loads(line)
            agent = row.get("agent", "unknown")
            
            if "tutor" in agent: agent = "rag_tutor"
            if "quiz" in agent: agent = "quiz_drafter"
            if "feedback" in agent: agent = "feedback_mentor"
            
            if agent in agent_data:
                agent_data[agent].append({
                    "prompt": row["prompt"],
                    "chosen": row["chosen"],
                    "rejected": row["rejected"],
                })

    return agent_data


def train(
    model_name: str,
    dataset_path: str,
    output_dir: str,
    max_steps: int,
    beta: float,
):
    from unsloth import PatchDPOTrainer
    PatchDPOTrainer()
    from unsloth import FastLanguageModel
    from trl import DPOConfig, DPOTrainer

    raw_data = load_and_filter_data(dataset_path)
    eligible_agents = [a for a, data in raw_data.items() if len(data) >= MIN_PAIRS_PER_AGENT]
    
    if not eligible_agents:
        logger.error("No agent reached the 50-pair threshold. Aborting.")
        return

    logger.info(f"Starting training for agents: {eligible_agents}")

    agent_metrics = {}

    for agent in eligible_agents:
        logger.info(f"── Loading Base Model for: {agent} ({len(raw_data[agent])} pairs) ──")
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=MAX_SEQ_LENGTH,
            dtype=None, 
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=16, lora_alpha=16, lora_dropout=0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )

        from unsloth.chat_templates import get_chat_template
        tokenizer = get_chat_template(tokenizer, chat_template="gemma")

        # Format dataset with standard Gemma chat template
        def format_dpo_pair(example):
            prompt_msgs = [{"role": "user", "content": example["prompt"]}]
            prompt_formatted = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
            
            full_chosen = tokenizer.apply_chat_template([
                {"role": "user", "content": example["prompt"]},
                {"role": "assistant", "content": example["chosen"]}
            ], tokenize=False)
            full_rejected = tokenizer.apply_chat_template([
                {"role": "user", "content": example["prompt"]},
                {"role": "assistant", "content": example["rejected"]}
            ], tokenize=False)
            
            example["prompt"] = prompt_formatted
            example["chosen"] = full_chosen[len(prompt_formatted):]
            example["rejected"] = full_rejected[len(prompt_formatted):]
            return example

        raw_dataset = Dataset.from_list(raw_data[agent])
        formatted_dataset = raw_dataset.map(format_dpo_pair)
        split_dataset = formatted_dataset.train_test_split(test_size=0.1, seed=42)
        
        training_args = DPOConfig(
            output_dir=f"{output_dir}/{agent}",
            max_steps=max_steps,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=5e-6,
            beta=beta,
            logging_steps=1,
            eval_strategy="steps",
            eval_steps=max_steps // 2,
            report_to="none",
        )

        trainer = DPOTrainer(
            model=model,
            args=training_args,
            train_dataset=split_dataset["train"],
            eval_dataset=split_dataset["test"],
            processing_class=tokenizer,
        )
        
        trainer.train()
        
        eval_results = trainer.evaluate()
        final_acc = eval_results.get("eval_rewards/accuracies", 0.0)
        logger.info(f"Intrinsic Reward Accuracy for {agent}: {final_acc:.4f}")
        agent_metrics[agent] = float(final_acc)

        model.save_pretrained(f"{output_dir}/adapters/{agent}")
        logger.info(f"Finished {agent}. Adapter saved.")

        logger.info(f"Exporting Isolated GGUF for {agent}...")
        model.save_pretrained_gguf(
            f"{output_dir}/gguf/{agent}", 
            tokenizer, 
            quantization_method="q4_k_m"
        )
        logger.info(f"Saved GGUF for {agent}.")

        del model
        del trainer
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()

    metrics_path = Path(output_dir) / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w") as f:
        json.dump(agent_metrics, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--max-steps", type=int, default=60)
    args = parser.parse_args()

    train(
        model_name=DEFAULT_MODEL,
        dataset_path=args.dataset,
        output_dir=args.output,
        max_steps=args.max_steps,
        beta=0.1
    )

if __name__ == "__main__":
    main()
