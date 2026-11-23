import { cpSync } from "node:fs";

// Next's standalone server needs its browser assets alongside the server bundle.
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
