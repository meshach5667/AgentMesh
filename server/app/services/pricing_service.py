def recommend_price(gpu_model: str, vram: int, region: str) -> float:
    base_price = 0.5
    if "H100" in gpu_model:
        return base_price + 3.0
    elif "A100" in gpu_model:
        return base_price + 2.0
    elif "4090" in gpu_model:
        return base_price + 0.5
    return base_price
