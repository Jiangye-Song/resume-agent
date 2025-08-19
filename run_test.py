import asyncio
import sys
from rag_run import rag_query, migrate_data

async def run_one(question):
    ans = await rag_query(question)
    print("\nAnswer:\n", ans)

async def run_from_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            q = line.strip()
            if not q:
                continue
            print(f"\nQuestion: {q}")
            await run_one(q)

async def interactive():
    print("Enter questions (type 'exit' to quit):")
    while True:
        try:
            q = input('> ')
        except EOFError:
            break
        if not q:
            continue
        if q.lower() in ('exit', 'quit'):
            break
        await run_one(q)

async def main():
    # Ensure data is migrated before queries
    await migrate_data()

    if len(sys.argv) >= 2:
        # First arg is either -f filename or the question itself
        if sys.argv[1] in ('-f', '--file') and len(sys.argv) >= 3:
            await run_from_file(sys.argv[2])
        else:
            question = ' '.join(sys.argv[1:])
            await run_one(question)
    else:
        await interactive()

if __name__ == '__main__':
    asyncio.run(main())
