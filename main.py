from fastapi import FastAPI, HTTPException, Request
import importlib
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

@app.post("/{script_name}")
async def run_script(script_name: str, request: Request):
    logging.info(f"Received request for script: {script_name}")
    try:
        # Add detailed logging before import
        logging.info(f"Attempting to import module: {script_name}")
        module = importlib.import_module(script_name)
        logging.info(f"Successfully imported module: {script_name}")

        # Execute the main function in the module
        data = await request.json()
        result = module.main(data)
        logging.info(f"Execution result: {result}")
        return {"result": result}
    except ImportError as e:
        logging.error(f"ImportError: {e}")
        raise HTTPException(status_code=404, detail=f"Script {script_name} not found")
    except Exception as e:
        logging.error(f"Error executing script {script_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
