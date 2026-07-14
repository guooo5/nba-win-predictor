import pandas as pd
df = pd.read_parquet("data/processed/training_data.parquet")
print(df.shape)
print(df.info())
print(df.head(5))
print(df.tail(5))
