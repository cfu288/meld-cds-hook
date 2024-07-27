# MELD CDS Hook

This repository contains a implementation of a Clinical Decision Support (CDS) hook for calculating the MELD score.

## Running in Development

To run the application in development mode, follow these steps:

1. Ensure you have Poetry installed. You can install it by following the instructions at [Poetry's official website](https://python-poetry.org/docs/#installation).

2. Install the project dependencies by running:

   ```bash
   poetry install
   ```

3. Start the development server with the following command:
   ```bash
   poetry run fastapi dev meld_cds_hook/main.py
   ```

You can test the CDS hook using the [CDS Hooks Sandbox](https://sandbox.cds-hooks.org/).

## Running Tests

To run the tests, execute the following command:

## Test with Sandbox

With the server running, you can test the CDS hook using the [CDS Hooks Sandbox](https://sandbox.cds-hooks.org/). Click on the settings gear in the top right corner and enter the following URL in the \*Enter discovery endpoint url" field: [http://localhost:8000/cds-services](http://localhost:8000/cds-services). Then hit save. The sandbox should now attempt to discover the CDS hook and you should see the MELD CDS card displayed.

## Test with pytest

```bash
poetry run pytest
```
