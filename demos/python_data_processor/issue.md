# Implement Data Processing Pipeline

Create a data processing system in `data_processor.py` that can:

1. **Load data from multiple formats**: Implement `load_csv(filename)` and `load_json(filename)` functions that return data as list of dictionaries
2. **Statistical analysis**: Implement `calculate_stats(data, column)` that returns a dictionary with mean, median, mode, std_dev, min, max for numeric columns
3. **Data filtering**: Implement `filter_data(data, filters)` where filters is a dict like `{"age": {"min": 18, "max": 65}, "city": ["New York", "Boston"]}`
4. **Data aggregation**: Implement `group_by_and_aggregate(data, group_column, agg_column, operation)` that groups data and applies operations like "sum", "avg", "count"
5. **Export functionality**: Implement `export_to_csv(data, filename)` and `export_to_json(data, filename)`
6. **Data validation**: Implement `validate_data(data, schema)` that checks if data conforms to a schema dict

The system should handle missing values gracefully and include comprehensive error handling. Make all tests pass with `python -m pytest`.
