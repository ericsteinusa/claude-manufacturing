import anthropic

client = anthropic.Anthropic() # reads ANTHROPIC_API_KEY from env

message = client.messages.create(
	model="claude-sonnet-4-6",
	max_tokens=1024,
	messages=[
		{"role": "user", "content": "Explain what an API is in 2 sentenances."}
	]
)

print(message.content[0].text)