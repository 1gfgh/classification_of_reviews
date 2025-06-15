import glob
import pandas as pd

path = '/Users/artem/Documents/Code/classification_of_reviews/mustapp'
filenames = glob.glob(path + "/*.csv")

dfs = []

for filename in filenames:
    dfs.append(pd.read_csv(filename))

print(dfs)

big_frame = pd.concat(dfs, ignore_index=True)

big_frame = big_frame.sort_values('Mustapp page ID')

print(big_frame)
print(big_frame.shape)

big_frame.to_csv(f"mustapp_reviews_total.csv", index=False)
