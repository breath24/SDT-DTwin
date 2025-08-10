import pytest
import os
import json
import csv
import tempfile
from data_processor import (
    load_csv, load_json, calculate_stats, filter_data,
    group_by_and_aggregate, export_to_csv, export_to_json, validate_data
)

# Test data
SAMPLE_DATA = [
    {"name": "Alice", "age": 30, "city": "New York", "salary": 75000},
    {"name": "Bob", "age": 25, "city": "Boston", "salary": 65000},
    {"name": "Charlie", "age": 35, "city": "New York", "salary": 85000},
    {"name": "Diana", "age": 28, "city": "Boston", "salary": 70000},
    {"name": "Eve", "age": 32, "city": "Chicago", "salary": 80000}
]

def test_load_csv():
    """Test CSV loading functionality."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["name", "age", "city", "salary"])
        writer.writeheader()
        writer.writerows(SAMPLE_DATA)
        temp_file = f.name
    
    try:
        data = load_csv(temp_file)
        assert len(data) == 5
        assert data[0]["name"] == "Alice"
        assert int(data[0]["age"]) == 30
    finally:
        os.unlink(temp_file)

def test_load_json():
    """Test JSON loading functionality."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(SAMPLE_DATA, f)
        temp_file = f.name
    
    try:
        data = load_json(temp_file)
        assert len(data) == 5
        assert data[0]["name"] == "Alice"
        assert data[0]["age"] == 30
    finally:
        os.unlink(temp_file)

def test_calculate_stats():
    """Test statistical calculations."""
    stats = calculate_stats(SAMPLE_DATA, "age")
    assert stats["mean"] == 30.0
    assert stats["min"] == 25
    assert stats["max"] == 35
    assert "median" in stats
    assert "std_dev" in stats

def test_calculate_stats_salary():
    """Test statistical calculations for salary."""
    stats = calculate_stats(SAMPLE_DATA, "salary")
    assert stats["mean"] == 75000
    assert stats["min"] == 65000
    assert stats["max"] == 85000

def test_filter_data_numeric():
    """Test numeric filtering."""
    filters = {"age": {"min": 28, "max": 32}}
    filtered = filter_data(SAMPLE_DATA, filters)
    assert len(filtered) == 3  # Alice (30), Diana (28), Eve (32)
    assert all(28 <= person["age"] <= 32 for person in filtered)

def test_filter_data_categorical():
    """Test categorical filtering."""
    filters = {"city": ["New York", "Boston"]}
    filtered = filter_data(SAMPLE_DATA, filters)
    assert len(filtered) == 4  # Everyone except Eve (Chicago)
    assert all(person["city"] in ["New York", "Boston"] for person in filtered)

def test_filter_data_combined():
    """Test combined filtering."""
    filters = {"age": {"min": 30}, "city": ["New York"]}
    filtered = filter_data(SAMPLE_DATA, filters)
    assert len(filtered) == 2  # Alice and Charlie

def test_group_by_and_aggregate_sum():
    """Test grouping and sum aggregation."""
    result = group_by_and_aggregate(SAMPLE_DATA, "city", "salary", "sum")
    assert result["New York"] == 160000  # Alice + Charlie
    assert result["Boston"] == 135000    # Bob + Diana
    assert result["Chicago"] == 80000    # Eve

def test_group_by_and_aggregate_avg():
    """Test grouping and average aggregation."""
    result = group_by_and_aggregate(SAMPLE_DATA, "city", "age", "avg")
    assert result["New York"] == 32.5    # (30 + 35) / 2
    assert result["Boston"] == 26.5      # (25 + 28) / 2
    assert result["Chicago"] == 32       # 32 / 1

def test_group_by_and_aggregate_count():
    """Test grouping and count aggregation."""
    result = group_by_and_aggregate(SAMPLE_DATA, "city", "name", "count")
    assert result["New York"] == 2
    assert result["Boston"] == 2
    assert result["Chicago"] == 1

def test_export_to_csv():
    """Test CSV export functionality."""
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        success = export_to_csv(SAMPLE_DATA[:2], temp_path)
        assert success is True
        
        # Verify the exported data
        with open(temp_path, 'r') as f:
            reader = csv.DictReader(f)
            exported_data = list(reader)
            assert len(exported_data) == 2
            assert exported_data[0]["name"] == "Alice"
    finally:
        os.unlink(temp_path)

def test_export_to_json():
    """Test JSON export functionality."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        success = export_to_json(SAMPLE_DATA[:2], temp_path)
        assert success is True
        
        # Verify the exported data
        with open(temp_path, 'r') as f:
            exported_data = json.load(f)
            assert len(exported_data) == 2
            assert exported_data[0]["name"] == "Alice"
    finally:
        os.unlink(temp_path)

def test_validate_data_valid():
    """Test data validation with valid data."""
    schema = {
        "name": {"type": "str", "required": True},
        "age": {"type": "int", "required": True, "min": 0, "max": 120},
        "salary": {"type": "int", "required": True, "min": 0}
    }
    result = validate_data(SAMPLE_DATA, schema)
    assert result["valid"] is True
    assert result["errors"] == []

def test_validate_data_invalid():
    """Test data validation with invalid data."""
    invalid_data = [
        {"name": "Alice", "age": -5, "salary": 75000},  # Invalid age
        {"age": 25, "salary": 65000},  # Missing required name
    ]
    schema = {
        "name": {"type": "str", "required": True},
        "age": {"type": "int", "required": True, "min": 0, "max": 120},
        "salary": {"type": "int", "required": True, "min": 0}
    }
    result = validate_data(invalid_data, schema)
    assert result["valid"] is False
    assert len(result["errors"]) > 0

def test_calculate_stats_missing_column():
    """Test stats calculation with non-existent column."""
    with pytest.raises(KeyError):
        calculate_stats(SAMPLE_DATA, "nonexistent_column")

def test_calculate_stats_non_numeric():
    """Test stats calculation with non-numeric column."""
    with pytest.raises(ValueError):
        calculate_stats(SAMPLE_DATA, "name")
