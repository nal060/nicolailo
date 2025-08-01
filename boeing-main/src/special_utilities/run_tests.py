import os
from test_evaluator import evaluate_all_test_types

def main():
    # Run evaluation for all test types
    print("Starting test evaluation...")
    results = evaluate_all_test_types(verbose=True)
    
    # Print summary for each test type
    print("\nDetailed Summary:")
    for test_type, test_results in results.items():
        if test_type == "overall":
            continue
            
        if "error" in test_results:
            print(f"\n{test_type}:")
            print(f"Error: {test_results['error']}")
        else:
            print(f"\n{test_type}:")
            print(f"Total Tests: {test_results['total_tests']}")
            print(f"Passed Tests: {test_results['passed_tests']}")
            print(f"Failed Tests: {test_results['failed_tests']}")
            print(f"Accuracy: {test_results['accuracy']:.2%}")
    
    # Print overall summary
    print("\nOverall Summary:")
    overall = results["overall"]
    print(f"Total Tests Across All Types: {overall['total_tests']}")
    print(f"Total Passed Tests: {overall['passed_tests']}")
    print(f"Overall Accuracy: {overall['accuracy']:.2%}")

if __name__ == "__main__":
    main() 