from fastapi import FastAPI, HTTPException, Request
import importlib

app = FastAPI()

@app.post("/{script_name}")
async def run_script(script_name: str, request: Request):
    try:
        # 동적으로 스크립트 모듈 import
        module = importlib.import_module(script_name)
        # 모듈에서 main 함수 실행
        data = await request.json()
        result = module.main(data)
        return {"result": result}
    except ImportError:
        raise HTTPException(status_code=404, detail=f"Script {script_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
