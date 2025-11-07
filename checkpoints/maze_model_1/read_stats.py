import pickle
with open("stats", "rb") as f:
    data = pickle.load(f)
print(type(data))
if isinstance(data, dict):
    print(data.keys())
    for k in data:
        if "return" in k:
            print(k, data[k][:5])  # Show first 5 values
else:
    print(data[:5])
