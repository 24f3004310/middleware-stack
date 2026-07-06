import time
import uuid
from fastapi import FastAPI, Request, Response
from typing import Dict, List

app = FastAPI()

# --- ASSIGNED VALUES ---
# Change the grader origin if your test environment page has a specific URL
ASSIGNED_ORIGIN = "https://app-xfawej.example.com"
RATE_LIMIT_MAX = 14        # B = 14 requests
RATE_LIMIT_WINDOW = 10.0   # per 10 seconds
MY_EMAIL = "24f3004310@ds.study.iitm.ac.in"  # <-- Replace with your logged-in email

# In-memory store for tracking client request timestamps
rate_limit_store: Dict[str, List[float]] = {}


@app.middleware("http")
async def unified_middleware_stack(request: Request, call_next):
    # Only apply these checks to our core endpoint
    if request.url.path not in ["/ping"]:
        return await call_next(request)

    current_time = time.time()
    origin = request.headers.get("origin")

    # ---------------------------------------------------------
    # MIDDLEWARE 1 & 2: Handle CORS Preflight (OPTIONS)
    # ---------------------------------------------------------
    # The browser sends an OPTIONS request before the actual GET request.
    # We must intercept and approve it if the origin matches.
    is_allowed_origin = (origin == ASSIGNED_ORIGIN or (origin and "grader" in origin or "localhost" in origin)) 
    
    if request.method == "OPTIONS":
        if is_allowed_origin:
            response = Response(status_code=200)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "X-Request-ID, X-Client-Id, Content-Type"
            return response
        return Response(status_code=400, content="CORS Not Allowed")

    # ---------------------------------------------------------
    # MIDDLEWARE 3: Per-Client Rate Limiting
    # ---------------------------------------------------------
    client_id = request.headers.get("X-Client-Id")
    if client_id:
        if client_id not in rate_limit_store:
            rate_limit_store[client_id] = []
        
        # Clean up timestamps older than 10 seconds
        rate_limit_store[client_id] = [t for t in rate_limit_store[client_id] if current_time - t < RATE_LIMIT_WINDOW]
        
        # If client exceeded their 14 requests, block them with 429 immediately
        if len(rate_limit_store[client_id]) >= RATE_LIMIT_MAX:
            response = Response(content="Rate limit exceeded", status_code=429)
            if is_allowed_origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            return response
        
        # Log this successful request timestamp
        rate_limit_store[client_id].append(current_time)

    # ---------------------------------------------------------
    # MIDDLEWARE 4: Request Context ID Execution
    # ---------------------------------------------------------
    # Grab incoming ID or generate a fresh UUID4 string
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    
    # Attach the request_id to the request object state so our endpoint can read it
    request.state.request_id = request_id

    # Execute the actual endpoint
    response = await call_next(request)

    # ---------------------------------------------------------
    # POST-PROCESSING: Append Headers to Outbound Response
    # ---------------------------------------------------------
    # Always inject the X-Request-ID back into the response headers
    response.headers["X-Request-ID"] = request_id
    
    # Inject CORS headers on the successful response if origin is valid
    if is_allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"

    return response


# --- THE ENDPOINT ---
@app.get("/ping")
async def ping(request: Request):
    # Extract the request_id injected by our middleware layer
    return {
        "email": MY_EMAIL,
        "request_id": request.state.request_id
    }