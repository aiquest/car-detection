import io

def read_process_stdout_unbufferred(process):
    # TODO: Extract utility function:
    finished_reading = False
    while not finished_reading:
        line = []
        is_carriage_return_line = False
        while True:
            inchar = process.stdout.read(1)
            # print repr(inchar)
            # Return is the line is complete:
            if inchar == '\r' or inchar == '\n':
                is_carriage_return_line = inchar == '\r'
                break

            # If the character is not empty or None:
            if inchar:
                line.append(inchar)

            # Note: poll returns the return code if the process is finished:
            elif process.poll() is not None:
                finished_reading = True
                is_carriage_return_line = False
                break
        line = ''.join(line)
        yield line, is_carriage_return_line


# Example:
# stream = subprocess.Popen(['ls'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=output_dir, bufsize=0)
# with open('file.txt') as fh:
#    stream_to_file_observing_cr(stream, fh)
def stream_to_file_observing_cr(stream, file_obj):
    last_line_begin_pos = file_obj.tell()
    for line, is_carriage_return_line in read_process_stdout_unbufferred(stream):
        # Write the line to disk, applying carriage returns:
        # Note: This avoids saving repeated status lines, while also
        # allowing status to be viewed by opening the file, or using
        #    $ tail -f file.txt.
        if is_carriage_return_line:
            if not last_line_begin_pos:
                last_line_begin_pos = file_obj.tell()
            file_obj.seek(last_line_begin_pos)
        else:
            last_line_begin_pos = None

        file_obj.write(line)
        if is_carriage_return_line:
            # Overwrite the line:
            file_obj.write(' ' * (80-len(line)))
        file_obj.write('\n')
        file_obj.flush()