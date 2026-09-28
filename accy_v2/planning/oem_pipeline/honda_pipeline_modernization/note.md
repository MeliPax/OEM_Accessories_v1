I want to clarify somethings:

Data loading:

- Honda will have two types of data loading options

  - This step aims to define how the project is run and data loaded
  - single file/single model: running the script for only one models/file. this way the pipeline will pick and run the file that was passed in the script.
  - Multi-file/model: running the the pipeline on all the files that are present in the most recent honda raw data directory.

  Note: I am think the process will be
  - validate :
  - check if it has English and French sheets as per the given instructions in the requirements document. To find legitimate parts data sheets, they have format : `*_APP_EN` and `*_APP_FR`
  - check sheets are non-nulls / not empty - First check  if it fails, we skip the file but the pipeline continues to other files

  - file load - load the sheets EN/FR into data frames

  - data extract and validation
  - grab the entire EN and FR sheets file from the extracted dfs
  - use an extract metadata helper to
  - validate that this is a legit Honda data sheets based on standard signature:
  - find Manufacture data signature, model name, model year and published data:
  - column counting starts from 1.
  - first: extract find the row that has the package sections keyword "1.0 Packages and Kits", and grab teh row top of it. in those rows there's a row that contains the following- file signature text: "Honda Accessories"
  - Model Name
  - Model Year
  - At the end this will return :
  Manufacture validated: true
  Model Name: value
  Model Year : value
  - Second:
  - Extract the last two non-empty rows in the main df.
  - check if they have a string that says "publication Date" in the 3rd column and save save a variable in the meta data that says found publication_date_string = True
  - and get the value in the second row and 3rd column, it's a date that has structure of 2026-04-15 (YYYY-MM-DD). I want you to validate it and save it as part of the meta data as publication year.

  - at the end of this, we will be having all the meta data and the extracted data in stored in a df ready for processing.
- Data extract process:

  - This section defines how data gets extracted step by step
  - 
- 

    At the end of load, all the data will be have been loaded into the

- When the excel file is loaded, as part of the meta data, I would like us to add a step to add the following:

  - For each legitimate data sheets EN/FR, grab the number grab the number of non null rows, overall, accounting for number of data rows that were loaded for logging purposes
- When it comes to reading the files, identifying sections:

  - load the files, loading data sheets for EN/FR based on defined instructions. We are not reading any other sheets on the file.
  -
