import numpy as np
import torch

# Simulate what happens
action_buffer = [np.zeros(2, dtype=np.float32) for _ in range(4)]

# Current approach
tensors = [torch.from_numpy(a).flatten().unsqueeze(0) for a in action_buffer]
print("Action buffer tensors:")
for i, t in enumerate(tensors):
    print(f"  {i}: shape={t.shape}, data={t}")

# Try to cat
try:
    act_buf = torch.cat(tensors, dim=1)
    print(f"\nConcatenated: shape={act_buf.shape}")
except Exception as e:
    print(f"\nError: {e}")

# What the model expects: batch_size x (buf_size * act_dim)
# But torch.cat(tuple_of_tensors, dim=1) concatenates along dim 1
# So if we have 4 tensors of shape [1, 2], cat dim=1 gives [1, 8] ✓

# Test
obs = torch.zeros(1, 4)
print(f"\nobs shape: {obs.shape}")
print(f"act_buf shape: {act_buf.shape if 'act_buf' in locals() else 'N/A'}")
