import { hashSeed, mulberry32 } from "./random.js";

export const PLATFORMS = {
  telephony: { idColumn: "telephony_id", productive: ["Available", "On Call", "After Call Work"], other: ["Not Ready", "Lunch", "Personal"] },
  chat: { idColumn: "chat_id", productive: ["Online", "Chatting"], other: ["Away", "Offline"] },
  ticketing: { idColumn: "ticketing_id", productive: ["Working Tickets", "Reviewing"], other: ["Unavailable"] },
};

const MIN_SEGMENT = 15;
const MAX_SEGMENT = 35;

export function stateInBlock({ platform, productive, agent, blockStart, minute }) {
  const states = productive ? PLATFORMS[platform].productive : PLATFORMS[platform].other;
  const rng = mulberry32(hashSeed(agent, platform, blockStart, productive));
  let cursor = blockStart;
  for (let i = 0; i < 1000; i++) {
    const length = MIN_SEGMENT + Math.floor(rng() * (MAX_SEGMENT - MIN_SEGMENT + 1));
    if (minute < cursor + length) return states[i % states.length];
    cursor += length;
  }
  return states[0];
}
