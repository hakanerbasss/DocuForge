from app.ai.deepseek import DeepSeekProvider

ai = DeepSeekProvider()

result = ai.generate(
    "Explain black holes in one short paragraph."
)

print(result)
