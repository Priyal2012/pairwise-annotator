"""Seed items: software-engineering prompts with two candidate answers each.

Written by hand to resemble real model output. In every pair one answer has a
concrete defect — a wrong claim, a missed edge case, an unsafe suggestion, or a
subtly broken snippet — and the other is the answer a careful engineer would
give. Which one is "A" varies so the data has no positional tell.
"""

SEED_ITEMS = [
    {
        "id": "sort-return",
        "prompt": "In Python, what's the difference between list.sort() and sorted()?",
        "response_a": (
            "list.sort() sorts the list in place and returns None, so `x = my_list.sort()` leaves x as None. "
            "sorted(iterable) returns a new sorted list and works on any iterable, not just lists. "
            "Both accept key= and reverse=. Use sort() when you don't need the original order and want to avoid a copy."
        ),
        "response_b": (
            "list.sort() sorts the list in place and returns the sorted list, so you can chain it: `my_list.sort().reverse()`. "
            "sorted() makes a copy and returns it. Use sorted() when you need to keep the original."
        ),
        "meta": {"topic": "python", "defect_in": "B", "defect": "sort() returns None, chaining breaks"},
    },
    {
        "id": "sql-injection",
        "prompt": "How do I safely build a SQL query in Python that filters users by a name the user typed in?",
        "response_a": (
            "Sanitise the input by escaping single quotes and then format the query:\n"
            'name = name.replace("\'", "\'\'")\n'
            "cur.execute(f\"SELECT * FROM users WHERE name = '{name}'\")\n"
            "This stops the classic ' OR 1=1 trick."
        ),
        "response_b": (
            "Never put user input into the SQL string. Use a parameterised query and let the driver handle quoting:\n"
            'cur.execute("SELECT * FROM users WHERE name = %s", (name,))\n'
            "(The placeholder is ? for sqlite3 and %s for psycopg2/MySQL.) Escaping by hand is fragile — it misses "
            "backslashes, encodings and driver-specific cases."
        ),
        "meta": {"topic": "security", "defect_in": "A", "defect": "hand-rolled escaping is not safe"},
    },
    {
        "id": "mutable-default",
        "prompt": "Why does this function keep accumulating values between calls?\n\ndef add(x, items=[]):\n    items.append(x)\n    return items",
        "response_a": (
            "Default argument values are evaluated once, when the function is defined, so every call that omits "
            "`items` shares the same list object. Use a sentinel instead:\n"
            "def add(x, items=None):\n    if items is None:\n        items = []\n    items.append(x)\n    return items"
        ),
        "response_b": (
            "Python passes lists by reference, so `items` points to the caller's list and keeps growing. "
            "Copy it on entry: `items = list(items)` as the first line, and the problem goes away."
        ),
        "meta": {
            "topic": "python",
            "defect_in": "B",
            "defect": "wrong diagnosis; copying doesn't fix the shared default",
        },
    },
    {
        "id": "git-undo-commit",
        "prompt": "I committed to the wrong branch (not pushed yet). How do I move that last commit to a new branch?",
        "response_a": (
            "git branch new-branch        # new branch pointing at the current commit\n"
            "git reset --hard HEAD~1      # move the wrong branch back one commit\n"
            "git checkout new-branch\n"
            "Since nothing was pushed, rewriting the local branch is safe. If you had uncommitted changes, "
            "use `git reset --keep HEAD~1` or stash first so --hard doesn't discard them."
        ),
        "response_b": (
            "git checkout -b new-branch\n"
            "git push --force\n"
            "That creates the branch with your commit and force-pushes so the remote matches. "
            "Then delete the commit from the old branch with `git revert HEAD`."
        ),
        "meta": {
            "topic": "git",
            "defect_in": "B",
            "defect": "force-push is unnecessary and risky; revert adds a new commit instead of moving it",
        },
    },
    {
        "id": "big-o-dict",
        "prompt": "Is checking `x in my_list` fast in Python? I'm doing it inside a loop over 100k items.",
        "response_a": (
            "`x in my_list` is O(n): Python scans the list. Inside a loop over 100k items that's up to 10^10 "
            "comparisons. Convert the list to a set once (`s = set(my_list)`) and test `x in s`, which is O(1) on "
            "average. The elements must be hashable; if they aren't, consider a dict keyed by an id."
        ),
        "response_b": (
            "Yes, `in` is implemented in C so it's effectively O(1) for lists as well as sets. "
            "100k items is small; you won't notice a difference."
        ),
        "meta": {"topic": "algorithms", "defect_in": "B", "defect": "list membership is O(n)"},
    },
    {
        "id": "float-equality",
        "prompt": "Why is 0.1 + 0.2 == 0.3 False in Python, and how should I compare floats?",
        "response_a": (
            "It's a Python bug in the float implementation; use the decimal module or round() everywhere. "
            "round(0.1 + 0.2, 1) == 0.3 is True."
        ),
        "response_b": (
            "0.1, 0.2 and 0.3 can't be represented exactly in binary floating point, so the rounded sum differs "
            "from the rounded 0.3 by one ulp. This is IEEE 754 behaviour, not a Python bug. Compare with a tolerance: "
            "math.isclose(a, b, rel_tol=1e-9) — or use decimal.Decimal when you need exact decimal arithmetic (money)."
        ),
        "meta": {
            "topic": "numerics",
            "defect_in": "A",
            "defect": "calls IEEE behaviour a bug; round() is not a general fix",
        },
    },
    {
        "id": "async-blocking",
        "prompt": "My FastAPI endpoint is `async def` but it still blocks other requests while it calls requests.get(). Why?",
        "response_a": (
            "requests is a synchronous library: requests.get() blocks the event loop thread, so no other coroutine "
            "can run until it returns. Either use an async client (httpx.AsyncClient with `await client.get(...)`), "
            "or run the blocking call in a thread: `await asyncio.to_thread(requests.get, url)`. Alternatively make "
            "the endpoint a plain `def`; FastAPI then runs it in a threadpool."
        ),
        "response_b": (
            "You need to add `await` in front of requests.get() — without it the call runs synchronously. "
            "Change it to `resp = await requests.get(url)` and the endpoint will stop blocking."
        ),
        "meta": {
            "topic": "concurrency",
            "defect_in": "B",
            "defect": "requests.get is not awaitable; this raises TypeError",
        },
    },
    {
        "id": "rest-idempotent",
        "prompt": "Which HTTP methods are idempotent, and why does it matter for retries?",
        "response_a": (
            "GET, HEAD, PUT, DELETE and OPTIONS are idempotent: repeating the request has the same effect as doing "
            "it once. POST is not (two POSTs may create two resources), and PATCH is not guaranteed to be. "
            "It matters because clients and proxies may safely retry idempotent requests after a timeout; for POST "
            "you need an idempotency key or a de-duplication check server-side."
        ),
        "response_b": (
            "Only GET is idempotent because it doesn't change anything. PUT, POST, PATCH and DELETE all modify "
            "state so they can't be retried safely. Use a retry loop only on GET."
        ),
        "meta": {"topic": "http", "defect_in": "B", "defect": "PUT and DELETE are idempotent by definition"},
    },
    {
        "id": "n-plus-one",
        "prompt": "My Django view is slow: it loops over 500 orders and prints order.customer.name. What's wrong?",
        "response_a": (
            "That's the N+1 query problem: one query for the orders, then one query per order to load its customer, "
            "501 queries in total. Fetch the relation in the same query with select_related:\n"
            "orders = Order.objects.select_related('customer')\n"
            "For many-to-many or reverse relations use prefetch_related. Verify with django-debug-toolbar or "
            "`len(connection.queries)` in a test."
        ),
        "response_b": (
            "Printing is slow in Python. Collect the names into a list first and print once with '\\n'.join(...). "
            "You can also add `@cache_page(60)` to the view so repeated loads are instant."
        ),
        "meta": {
            "topic": "databases",
            "defect_in": "B",
            "defect": "misses the N+1 cause; caching hides rather than fixes",
        },
    },
    {
        "id": "unit-test-time",
        "prompt": "How should I unit-test a function that uses datetime.now() to decide whether a token has expired?",
        "response_a": (
            "Pass time in as a dependency: give the function a `now` parameter (default `datetime.now`) or inject a "
            "clock object, then tests call it with fixed datetimes for 'just before' and 'just after' expiry. "
            "If you can't change the signature, patch the name where it's looked up "
            "(`unittest.mock.patch('mymodule.datetime')`) or use the freezegun library. "
            "Avoid tests that sleep until a real expiry — they're slow and flaky."
        ),
        "response_b": (
            "Create a token with a 1-second lifetime, call the function, time.sleep(2), and call it again to check it "
            "has expired. This tests the real behaviour instead of mocking."
        ),
        "meta": {"topic": "testing", "defect_in": "B", "defect": "sleep-based tests are slow and flaky"},
    },
    {
        "id": "password-storage",
        "prompt": "What's the right way to store user passwords in a web app?",
        "response_a": (
            "Hash them with SHA-256 plus a per-user salt and store hash+salt. SHA-256 is cryptographically secure "
            "and fast, so login stays snappy even with many users."
        ),
        "response_b": (
            "Use a slow, salted password hash designed for the job: bcrypt, scrypt or Argon2id (e.g. "
            "`argon2-cffi` or `bcrypt` in Python). Fast hashes like SHA-256 — even salted — can be brute-forced "
            "at billions of guesses per second on a GPU. Store only the hash, set a work factor you re-tune over "
            "time, and never log or email passwords."
        ),
        "meta": {"topic": "security", "defect_in": "A", "defect": "fast hash is unsuitable for passwords"},
    },
    {
        "id": "shallow-copy",
        "prompt": "I copied a list of lists with `b = a[:]` but changing b[0][0] also changes a. Why?",
        "response_a": (
            "`a[:]` is a shallow copy: b is a new outer list, but its elements are the *same* inner list objects as "
            "in a. Mutating an inner list is visible through both. Use `copy.deepcopy(a)` for a full copy, or "
            "`[row[:] for row in a]` when you know it's exactly two levels deep."
        ),
        "response_b": (
            "Slicing a list returns a view, like NumPy arrays, so b and a share memory. "
            "Use `b = list(a)` instead, which allocates a real copy."
        ),
        "meta": {
            "topic": "python",
            "defect_in": "B",
            "defect": "list slices are copies, not views; list(a) is also shallow",
        },
    },
]
