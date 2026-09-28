import pandas as pd
import glob
import os
import re


# ============================================================
# PATHS
# ============================================================

# Location of this Python file:
# backend/member1/data_preprocessing.py

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Go from member1 -> backend -> data
DATA_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data")
)

# Search inside the entire data folder
DATASET_SEARCH_PATH = os.path.join(
    DATA_DIR,
    "**",
    "*tweets_labeled.csv"
)

# Master dataset output
OUTPUT_PATH = os.path.join(
    DATA_DIR,
    "CrisisSense_Master_Dataset.csv"
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    text = str(text).lower()

    # Remove URLs
    text = re.sub(
        r"http\S+|www\S+",
        "",
        text
    )

    # Remove mentions
    text = re.sub(
        r"@\w+",
        "",
        text
    )

    # Remove hashtag symbol
    text = re.sub(
        r"#",
        "",
        text
    )

    # Keep letters and spaces
    text = re.sub(
        r"[^a-zA-Z\s]",
        " ",
        text
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# LOAD DATASET
# ============================================================

def load_dataset():

    print("\nSearching for CrisisLex labeled CSV files...")

    csv_files = glob.glob(
        DATASET_SEARCH_PATH,
        recursive=True
    )

    print(
        "CSV files found:",
        len(csv_files)
    )

    if len(csv_files) == 0:

        print("\nPython searched here:")
        print(DATA_DIR)

        raise FileNotFoundError(
            "\nNo CrisisLex labeled CSV files found.\n"
            "Make sure the extracted CrisisLexT26 folder "
            "is inside backend/data/"
        )

    data = []

    for file in csv_files:

        print(
            "Reading:",
            os.path.basename(file)
        )

        df = pd.read_csv(file)

        # Remove spaces from column names
        df.columns = df.columns.str.strip()

        # Event name = parent folder
        event = os.path.basename(
            os.path.dirname(file)
        )

        df["Event"] = event

        data.append(df)

    # Combine all 26 events
    dataset = pd.concat(
        data,
        ignore_index=True
    )

    return dataset


# ============================================================
# PREPROCESS DATASET
# ============================================================

def preprocess_dataset(dataset):

    print("\nPreprocessing dataset...")

    # Check required column
    if "Tweet Text" not in dataset.columns:

        raise ValueError(
            "'Tweet Text' column not found."
        )

    # Remove missing tweets
    dataset = dataset.dropna(
        subset=["Tweet Text"]
    ).copy()

    # Convert to string
    dataset["Tweet Text"] = dataset[
        "Tweet Text"
    ].astype(str)

    # Remove duplicate tweets
    before = len(dataset)

    dataset = dataset.drop_duplicates(
        subset=["Tweet Text"]
    )

    after = len(dataset)

    print(
        "Duplicate tweets removed:",
        before - after
    )

    # Create cleaned text
    dataset["Clean_Text"] = dataset[
        "Tweet Text"
    ].apply(clean_text)

    # Remove empty text
    dataset = dataset[
        dataset["Clean_Text"].str.strip() != ""
    ].copy()

    return dataset


# ============================================================
# DISPLAY DATASET INFORMATION
# ============================================================

def display_dataset_information(dataset):

    print("\n" + "=" * 60)
    print("DATASET INFORMATION")
    print("=" * 60)

    print(
        "\nTotal records:",
        len(dataset)
    )

    print(
        "Total columns:",
        len(dataset.columns)
    )

    print(
        "Total events:",
        dataset["Event"].nunique()
    )

    print("\nColumns:")
    print(
        dataset.columns.tolist()
    )

    # --------------------------------------------------------
    # Informativeness
    # --------------------------------------------------------

    if "Informativeness" in dataset.columns:

        print("\n" + "-" * 60)
        print("INFORMATIVENESS")
        print("-" * 60)

        print(
            dataset[
                "Informativeness"
            ].value_counts(
                dropna=False
            )
        )

    # --------------------------------------------------------
    # Information Type
    # --------------------------------------------------------

    if "Information Type" in dataset.columns:

        print("\n" + "-" * 60)
        print("INFORMATION TYPE")
        print("-" * 60)

        print(
            dataset[
                "Information Type"
            ].value_counts(
                dropna=False
            )
        )

    # --------------------------------------------------------
    # Information Source
    # --------------------------------------------------------

    if "Information Source" in dataset.columns:

        print("\n" + "-" * 60)
        print("INFORMATION SOURCE")
        print("-" * 60)

        print(
            dataset[
                "Information Source"
            ].value_counts(
                dropna=False
            )
        )

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    print("\n" + "-" * 60)
    print("MISSING VALUES")
    print("-" * 60)

    print(
        dataset.isnull().sum()
    )


# ============================================================
# SAVE DATASET
# ============================================================

def save_dataset(dataset):

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    dataset.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("\n" + "=" * 60)
    print("MASTER DATASET SAVED")
    print("=" * 60)

    print(
        OUTPUT_PATH
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("CRISISSENSE - MEMBER 1")
    print("DATA PREPROCESSING")
    print("=" * 60)

    # Load
    dataset = load_dataset()

    print(
        "\nOriginal dataset shape:",
        dataset.shape
    )

    # Preprocess
    dataset = preprocess_dataset(
        dataset
    )

    print(
        "\nProcessed dataset shape:",
        dataset.shape
    )

    # Information
    display_dataset_information(
        dataset
    )

    # Save
    save_dataset(
        dataset
    )

    # Preview
    print("\nFirst 5 records:")
    print(
        dataset.head()
    )

    print(
        "\nPreprocessing completed successfully!"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()