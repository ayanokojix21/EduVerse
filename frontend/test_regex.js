const content = "<think>\nTesting thinking...\nStill thinking\n</think>\n\nHere is the answer.";
console.log(content.replace(/<think>/g, '<details className="think-block"><summary>Thinking...</summary>').replace(/<\/think>/g, '</details>'));
