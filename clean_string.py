def clean_string(input_string: str) -> str:
  """
  Cleans a multi-line string by trimming whitespace and removing empty lines.

  This function takes a string, splits it into lines, removes any leading or
  trailing whitespace from each line, discards any lines that become empty
  after trimming, and then joins the non-empty lines back together with
  a single newline character between them.

  Args:
    input_string: The string to be cleaned.

  Returns:
    A new string with whitespace-trimmed lines and no empty lines.
  """
  # Use a list comprehension for a concise solution:
  # 1. input_string.split('\n'): Splits the string into a list of lines.
  # 2. line.strip(): Removes leading/trailing whitespace from each line.
  # 3. if line.strip(): This condition filters out any strings that are empty
  #    after being stripped of whitespace.
  # 4. '\n'.join(...): Joins the elements of the resulting list into a
  #    single string, with each element separated by a newline.
  cleaned_lines = [line.strip() for line in input_string.split('\n') if line.strip()]
  return '\n'.join(cleaned_lines)
