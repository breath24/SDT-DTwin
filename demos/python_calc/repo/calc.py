"""
A very simple calculator module.
"""

def add(x, y):
    """Adds two numbers."""
    return x + y

def subtract(x, y):
    """Subtracts the second number from the first."""
    return x - y

# --- Main execution block (optional, for simple command-line use) ---
if __name__ == "__main__":
    print("Simple Calculator App")
    num1 = float(input("Enter first number: "))
    num2 = float(input("Enter second number: "))

    print(f"{num1} + {num2} = {add(num1, num2)}")
    print(f"{num1} - {num2} = {subtract(num1, num2)}")
