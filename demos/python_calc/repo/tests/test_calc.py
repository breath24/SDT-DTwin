"""
Unit tests for the calculator module.
"""

import pytest
from calculator import add, subtract # Import functions from calculator.py

def test_add_positive_numbers():
  """Test adding two positive numbers."""
  assert add(2, 3) == 5
  assert add(10, 5) == 15

def test_add_negative_numbers():
  """Test adding two negative numbers."""
  assert add(-2, -3) == -5
  assert add(-10, -5) == -15

def test_add_mixed_numbers():
  """Test adding a positive and a negative number."""
  assert add(5, -3) == 2
  assert add(-10, 5) == -5

def test_add_zero():
  """Test adding zero."""
  assert add(5, 0) == 5
  assert add(0, -3) == -3
  assert add(0, 0) == 0

def test_subtract_positive_numbers():
  """Test subtracting positive numbers."""
  assert subtract(5, 3) == 2
  assert subtract(10, 5) == 5

def test_subtract_negative_result():
  """Test subtraction resulting in a negative number."""
  assert subtract(3, 5) == -2
  assert subtract(-2, 3) == -5

def test_subtract_negative_numbers():
  """Test subtracting negative numbers."""
  assert subtract(-5, -3) == -2 # -5 - (-3) = -5 + 3 = -2
  assert subtract(-3, -5) == 2  # -3 - (-5) = -3 + 5 = 2

def test_subtract_zero():
  """Test subtracting zero."""
  assert subtract(5, 0) == 5
  assert subtract(0, 5) == -5
  assert subtract(0, 0) == 0

# Add more tests as needed!