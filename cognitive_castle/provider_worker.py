"""Private serial stdio worker; one process is bound to one host trust domain."""

import argparse
import json
import os
from pathlib import Path
import sys

from .memory_types import MemoryError, SourceExpectation
from .provider_protocol import MAX_FRAME_BYTES, decode_request, response


def serve(service, source, output):
    recent_ids = []
    while True:
        frame = source.readline(MAX_FRAME_BYTES + 1)
        if not frame:
            return
        request_id = "invalid"
        close = False
        try:
            request = decode_request(frame)
            request_id, op, args = request["id"], request["op"], request["args"]
            if request_id in recent_ids:
                raise MemoryError("invalid_request")
            recent_ids.append(request_id)
            del recent_ids[:-1024]
            if op in {"hello", "health"}:
                result = service.health().as_dict()
            elif op == "close":
                result, close = {}, True
            elif op == "snapshot":
                ids = args.get("record_ids")
                if not isinstance(ids, list):
                    raise MemoryError("invalid_request")
                expected = args.get("expected")
                if expected is not None:
                    if not isinstance(expected, dict):
                        raise MemoryError("invalid_request")
                    try:
                        expected = {k: SourceExpectation(**v) for k, v in expected.items()}
                    except (TypeError, ValueError):
                        raise MemoryError("invalid_request") from None
                result = service.snapshot(
                    tuple(ids), expected=expected, maximum_bytes=args.get("maximum_bytes", 262144)
                ).as_dict()
            else:
                result = getattr(service, op)(**args).as_dict()
            reply = response(request_id, result=result)
        except MemoryError as exc:
            reply = response(request_id, error=exc.code)
        except (TypeError, UnicodeError, ValueError):
            reply = response(request_id, error="invalid_request")
        except Exception:
            reply = response(request_id, error="unavailable")
        output.write(reply)
        output.flush()
        if close or len(frame) > MAX_FRAME_BYTES or not frame.endswith(b"\n"):
            return


def _open_service(args):
    from .config import CognitiveCastleConfig
    from .context import CastleContext, PalacePaths
    from .memory import MemoryService

    config_path = Path(args.config)
    if (
        not config_path.is_absolute()
        or not config_path.is_file()
        or not Path(args.palace).is_absolute()
    ):
        raise MemoryError("incompatible_store")
    context = None
    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config_data, dict):
            raise ValueError()
        config = CognitiveCastleConfig(config_dir=config_path.parent)
        config._file_config = config_data
        paths = PalacePaths.resolve(args.palace, config_dir=config_path.parent)
        context = CastleContext.open(paths, config=config, read_only=True)
        service = MemoryService(
            context, namespace=args.namespace, allowed_wings=frozenset(args.wing)
        )
    except MemoryError:
        if context is not None:
            context.close()
        raise
    except Exception:
        if context is not None:
            context.close()
        raise MemoryError("incompatible_store") from None
    try:
        service.health()  # Refuse an unreadable store before loading any models.
        # This process is a single trust domain. Disallow hub downloads on
        # serving traffic, even if the parent has different hub preferences.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from .embedding import _get_model
        from .reranker import rerank

        if getattr(context.get_collection(), "dense_available", True):
            _get_model(context.config.embedding_device, cfg=context.config)
        device = "cpu" if context.config.embedding_device in {"cpu", "mps"} else "auto"
        rerank("local preflight", ["local preflight"], device=device, cfg=context.config)
    except Exception:
        context.close()
        raise MemoryError("unavailable") from None
    return context, service


class _UnavailableService:
    def __init__(self, error):
        self.error = error

    def __getattr__(self, _name):
        def unavailable(*_args, **_kwargs):
            raise MemoryError(self.error)

        return unavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palace", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--wing", action="append", required=True)
    args = parser.parse_args()
    # Worker-only fd protection covers Python prints and native dependencies.
    # Importing this module never alters the embedding application's stdio.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    context = None
    try:
        try:
            context, service = _open_service(args)
        except MemoryError as exc:
            service = _UnavailableService(exc.code)
        serve(service, sys.stdin.buffer, output)
    finally:
        if context is not None:
            context.close()
        output.close()


if __name__ == "__main__":
    main()
