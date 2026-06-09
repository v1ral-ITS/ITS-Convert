#!/usr/bin/env python3
"""Demo script showcasing all supported constructs."""

import os
import sys

# Variables
name = "World"
count = 42
pi = 3.14
active = True

# Print
print("Hello,", name)
print(f"You have {count} messages")

# Input
username = input("What is your name? ")

# If / elif / else
if count > 50:
    print("Many messages")
elif count > 10:
    print("Some messages")
else:
    print("Few messages")

# For range
for i in range(5):
    print(f"Item {i}")

# For range with step
for i in range(0, 20, 5):
    print(f"Step {i}")

# For in list
fruits = ["apple", "banana", "cherry"]
for fruit in fruits:
    print(fruit)

# While
x = 0
while x < 3:
    print(f"x = {x}")
    x += 1

# Function
def greet(name, greeting="Hello"):
    message = f"{greeting}, {name}!"
    print(message)
    return message

result = greet("Alice")

# Try / except
try:
    value = int("not a number")
except ValueError as e:
    print(f"Error: {e}")
finally:
    print("Done")

# Environment variables
home = os.environ.get("HOME", "/tmp")
print(f"Home: {home}")

# Exit
sys.exit(0)
