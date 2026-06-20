#!/usr/bin/env bash
# Extract a tar archive to a target directory.
# Reference: https://github.com/blinksh/snippets/blob/main/tar/extract.sh
archive_name="myarchive"
extension="gz"
to_path="/tmp/extracted"
tar xvf ${archive_name}.tar.${extension} -C ${to_path}
