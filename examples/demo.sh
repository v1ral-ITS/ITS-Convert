#!/usr/bin/env bash
# Demo bash script for round-trip testing

name="World"
count=42
echo "Hello, $name"

read -r -p "What is your name? " username

if [ "$count" -gt 50 ]; then
    echo "Many messages"
elif [ "$count" -gt 10 ]; then
    echo "Some messages"
else
    echo "Few messages"
fi

for (( i=0; i<5; i++ )); do
    echo "Item $i"
done

x=0
while [ "$x" -lt 3 ]; do
    echo "x = $x"
    x=$(( x + 1 ))
done

greet() {
    local name="$1"
    echo "Hello, $name!"
}

greet "Alice"

exit 0
