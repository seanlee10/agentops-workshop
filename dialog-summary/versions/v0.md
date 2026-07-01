# Dialogue Summary Skill

## Description

Use this skill when the user asks you to summarize a short dialogue, chat transcript, messenger conversation, or meeting-like exchange.

## Goal

Create a concise summary that captures the main point of the conversation, including important decisions, requests, plans, or emotional context when relevant.

## Input

The input is usually a speaker-labeled dialogue. Each line may contain a speaker name followed by their message.

Example:

Alice: Are you coming to dinner tonight?
Bob: I might be late because of work.
Alice: That's okay. I'll save you some food.

## Procedure

1. Read the full dialogue before summarizing.
2. Identify the main participants.
3. Identify the main topic of the conversation.
4. Extract important decisions, requests, plans, problems, or commitments.
5. Ignore greetings, small talk, filler expressions, and repeated information unless they change the meaning.
6. Write a concise summary in natural language.

## Output Format

Write only the final summary.

The summary should be 1–3 sentences.

## Rules

* Do not add information that is not supported by the dialogue.
* Do not confuse who said or wanted what.
* Preserve important names, dates, times, places, and commitments.
* Prefer a clear third-person summary.
* Do not quote the dialogue unless the exact wording is important.

## Quality Checklist

Before finalizing, check:

* Does the summary capture the main point?
* Are the speakers' intentions represented correctly?
* Are concrete plans, requests, or decisions included?
* Is irrelevant small talk removed?
* Is the summary concise?
