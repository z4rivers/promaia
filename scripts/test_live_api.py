from google import genai
client = genai.Client()
print(dir(client.aio))
if hasattr(client.aio, 'live'):
    print("Live API available!")
else:
    print("Live API not found.")
