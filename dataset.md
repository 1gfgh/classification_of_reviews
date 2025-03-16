# Dataset Description
[Dataset directory](https://drive.google.com/drive/folders/1Bpa7CyEr9EaRoYFfDqEKEaRMPfz0CjNO?usp=drive_link)

This dataset is created for analyzing reviews, providing insights into user feedback and ratings. Below is a breakdown of each column in the dataset:

## Columns

### 1. `Name`
- **Type:** String
- **Description:** The name of the product or good being reviewed. This helps associate reviews with specific items.

### 2. `Description`
- **Type:** String
- **Description:** A brief description of the product to provide context for the review.

### 3. `Review`
- **Type:** String
- **Description:** A written review from a user or customer, containing their opinions, experiences, or feedback about the product.

### 4. `Rating`
- **Type:** Integer
- **Description:** A numerical rating given by the reviewer, reflecting their satisfaction with the product. The scale of the rating depends on source now(1-5 for WB and Lamoda, 1-10 for MustApp)

## Basic Info

We get data from follow source: Lamoda, MustApp and WildBerries. The dataset consists of product reviews, containing 486,920 records. It includes four columns: product name (`Name`), description (`Description`), text review (`Review`), and numerical rating (`Rating`). The Description column has missing values since not all products come with detailed descriptions. However, there are quite few misses relative to the amount of all data we have. The average product rating is approximately 8.71, but the distribution is highly skewed towards the maximum value. The histogram shows that over 60% of the reviews have a rating of 10. The Review column contains unique symbols such as emojis, requiring additional text processing before analysis.

## More Info

You can read more about EDA and conclusions [here.](EDA/EDA.md)
