from fastapi import FastAPI, HTTPException, Request
import importlib
import logging
import traceback
import asyncio

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.post("/{script_name}")
async def run_script(script_name: str, request: Request):
    logging.info(f"Received request for script: {script_name}")
    try:
        logging.info(f"Attempting to import module: {script_name}")
        module = importlib.import_module(script_name)
        logging.info(f"Successfully imported module: {script_name}")

        data = await request.json()
        
        # 비동기 실행으로 변경
        result = await asyncio.to_thread(module.main, data)
        
        logging.info(f"Execution result: {result}")
        return {"result": result}
    except ImportError as e:
        logging.error(f"ImportError: {e}")
        raise HTTPException(status_code=404, detail=f"Script {script_name} not found")
    except Exception as e:
        logging.error(f"Error executing script {script_name}: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
