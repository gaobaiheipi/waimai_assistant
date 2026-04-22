import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

local_path = "./models/Qwen/Qwen2.5-0.5B-Instruct"

print("测试 1: 加载 tokenizer...")
try:
    tokenizer = AutoTokenizer.from_pretrained(local_path, trust_remote_code=True)
    print("✓ Tokenizer 成功")
except Exception as e:
    print(f"✗ Tokenizer 失败: {e}")

print("\n测试 2: 检查模型文件...")
import os
model_file = os.path.join(local_path, "model.safetensors")
if os.path.exists(model_file):
    size = os.path.getsize(model_file)
    print(f"✓ 模型文件存在: {size} bytes ({size/1024/1024:.1f} MB)")
    if size < 900000000:  # 小于 900MB
        print("✗ 模型文件不完整！")
else:
    print("✗ 模型文件不存在")

print("\n测试 3: 尝试加载模型...")
try:
    # 最简加载
    model = AutoModelForCausalLM.from_pretrained(
        local_path,
        trust_remote_code=True,
        local_files_only=True
    )
    print("✓ 模型加载成功")
except Exception as e:
    print(f"✗ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()

input("\n按回车退出...")
