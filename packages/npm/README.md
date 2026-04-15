# @gradata/cli

Node wrapper and JS correction-event client for [Gradata](https://github.com/Gradata/gradata) — procedural memory for AI agents.

## Install

```bash
npm i -g @gradata/cli
# or use without installing:
npx @gradata/cli --help
```

Requires Node 18+. For the full SDK (rule synthesis, graduation pipeline, manifest) install the Python package too:

```bash
pip install gradata
```

## Usage

### Emit a correction from JS/TS

The daemon converts correction events into behavioural rules via the graduation pipeline. Start the daemon once:

```bash
python -m gradata.daemon --brain-dir ./brain --port 8765
# or: docker run -p 8765:8765 -v $(pwd)/brain:/brain gradata/daemon
```

Then from your Node app:

```ts
import { GradataClient } from "@gradata/cli";

const client = new GradataClient({ endpoint: "http://127.0.0.1:8765" });

await client.correct({
  draft: "We are pleased to inform you of our new product offering.",
  final: "Hey, check out what we just shipped.",
  outputType: "email",
});
```

### CLI wrapper

```bash
# Direct JS path (no Python needed for this subcommand):
gradata correct --draft "formal version" --final "casual version" --type email

# Any other subcommand shells to `python -m gradata <args>`:
gradata init ./brain
gradata search "budget objections"
gradata manifest
```

## API

`new GradataClient(opts)`

| Option      | Type      | Default                      |
| ----------- | --------- | ---------------------------- |
| `endpoint`  | `string`  | `http://127.0.0.1:8765`      |
| `timeoutMs` | `number`  | `5000`                       |
| `fetch`     | `fetch`   | `globalThis.fetch`           |

Methods:

- `correct({ draft, final, outputType?, taskType?, selfScore?, metadata? })` — posts to `/correct`.
- `health()` — pings `/health`, returns `{ ok, sdk_version, sessions }`.

## Environment

| Variable              | Purpose                                                    |
| --------------------- | ---------------------------------------------------------- |
| `GRADATA_DAEMON_URL`  | Daemon endpoint used by the CLI `correct` subcommand.      |
| `GRADATA_PYTHON`      | Python binary used when shelling out to the Python SDK.    |

## License

AGPL-3.0-or-later. See `LICENSE` at the repository root.
