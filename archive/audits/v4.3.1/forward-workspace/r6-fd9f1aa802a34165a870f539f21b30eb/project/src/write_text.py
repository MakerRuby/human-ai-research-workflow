import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description="Write one fresh synthetic text file.")
parser.add_argument("--input", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--label", required=True)
args = parser.parse_args()
root = Path.cwd().resolve()
source = (root / args.input).resolve()
configuration = (root / args.config).resolve()
output = (root / args.output).resolve()
for path in (source, configuration, output):
    if root not in path.parents:
        raise ValueError("Path must remain inside the synthetic project")
config = json.loads(configuration.read_text(encoding="utf-8"))
text = f"fixture={config['fixture']}\nlabel={args.label}\n" + source.read_text(encoding="utf-8")
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(text)
print(json.dumps({"written": args.output, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "synthetic_only": True}, ensure_ascii=False))
