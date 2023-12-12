# Open the input file for reading
with open("episodes.txt", "r") as input_file:
    # Initialize an empty dictionary to store the lines by year
    lines_by_year = {}

    # Read the file line by line
    for line in input_file:
        # Extract the last four digits from the line
        year = line.strip()[-4:]

        # Add the line to the list of lines for this year
        if year in lines_by_year:
            lines_by_year[year].append(line)
        else:
            lines_by_year[year] = [line]

# Write each group of lines to a new file
for year, lines in lines_by_year.items():
    # Construct the output file name based on the year
    output_file_name = f"by_year/{year}.txt"

    # Write the lines to the output file
    with open(output_file_name, "w") as output_file:
        output_file.writelines(lines)
