# Security and privacy policy

Invigil listens to radio signals from devices that belong to real people, so a privacy problem here is a security problem.

## How to report

**Do not open a public issue for a privacy or security problem.**

Report it through GitHub private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**, or open <https://github.com/mohanvd/invigil/security/advisories/new>.
3. Describe the problem, how to reproduce it, and what data or behavior is affected.

Only the maintainers can see the report. Do not paste raw MAC addresses, real salts, passwords or raw captures into it. Describe them instead, and we will arrange a safe way to share anything we need.

## In scope

- Anything that could leak a raw Bluetooth address: to disk, to the broker, to the dashboard, to logs, or into this repository.
- Anything that could leak a hash salt or let someone recover addresses from hashes.
- Anything that could make the unit transmit, jam or interfere with a signal. The unit must be receive only.
- Leaks of Wi-Fi or MQTT credentials, or a way to read or inject readings on the broker without them.
- A secret, raw capture or personal data found in this repository or its history.
- Storage of audio or packet payloads.

## Out of scope

- A broker you run with anonymous access. That mode is for local testing with fake data only.
- Problems that need physical access to an unlocked laptop or to the unit.
- Bugs in Mosquitto, the Pico SDK, BTstack or Python packages. Report those to their own projects. Tell us if Invigil uses them in an unsafe way.

## What to expect

This is a student project with no paid staff. We aim to reply within 7 days and to fix confirmed problems as fast as school allows. We will credit you in the fix unless you ask us not to.

## Supported versions

Only the latest commit on `main` is supported. There are no releases yet.
