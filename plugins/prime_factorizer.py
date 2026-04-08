async def run(query: str) -> str | dict:
    """
    Factorizes an integer into its prime factors.
    Returns a dict with the list of factors and the original input,
    or an error message if the input is invalid.
    """
    try:
        n = int(query)
        if n < 2:
            return {"error": "Number must be >= 2"}
        factors = []
        divisor = 2
        while divisor * divisor <= n:
            while n % divisor == 0:
                factors.append(divisor)
                n //= divisor
            # After 2, check only odd numbers            divisor = divisor + 1 if divisor == 2 else divisor + 2
        if n > 1:
            factors.append(n)
        return {"factors": factors, "original": query}
    except ValueError:
        return {"error": "Input must be a valid integer"}