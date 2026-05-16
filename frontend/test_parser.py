import re

text = """Some prefix text before thinking.
<think>
This is the thinking process.
Step 1: Do something
Step 2: Do something else
</think>
And the final answer here.
"""

matches = list(re.finditer(r'<think>(.*?)</think>', text, re.DOTALL))
print("Matches:", len(matches))
if matches:
    print("Content:", repr(matches[0].group(1)))

parts = re.split(r'(<think>.*?</think>)', text, flags=re.DOTALL)
print("Parts:", parts)
