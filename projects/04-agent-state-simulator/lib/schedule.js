export const MINUTES_PER_WEEK = 7 * 24 * 60;
const WEEKDAYS = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };

export function minuteOfWeek(epochMs, timeZone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
      .formatToParts(new Date(epochMs))
      .map((p) => [p.type, p.value]),
  );
  return WEEKDAYS[parts.weekday] * 1440 + Number(parts.hour) * 60 + Number(parts.minute);
}

function localMinuteOfWeek(localIso) {
  const [date, time = "00:00"] = localIso.split(/[T ]/);
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
  return weekday * 1440 + hh * 60 + mm;
}

export class WeeklySchedule {
  constructor() {
    this.slots = new Map();
  }

  static fromRows(rows) {
    const schedule = new WeeklySchedule();
    for (const row of rows) {
      const start = localMinuteOfWeek(row.start);
      let duration = (Date.parse(`${row.end.replace(" ", "T")}Z`) - Date.parse(`${row.start.replace(" ", "T")}Z`)) / 60_000;
      if (!(duration > 0)) continue;
      duration = Math.min(duration, MINUTES_PER_WEEK);
      const slot = { activity: row.activity, productive: row.type?.toLowerCase() === "productive" };
      const end = start + duration;
      if (end <= MINUTES_PER_WEEK) schedule.add(row.agent, start, end, slot);
      else {
        schedule.add(row.agent, start, MINUTES_PER_WEEK, slot);
        schedule.add(row.agent, 0, end - MINUTES_PER_WEEK, slot);
      }
    }
    return schedule;
  }

  add(agent, start, end, slot) {
    const list = this.slots.get(agent) ?? [];
    list.push({ start, end, ...slot });
    this.slots.set(agent, list);
  }

  at(agent, minute) {
    return (this.slots.get(agent) ?? []).find((s) => minute >= s.start && minute < s.end) ?? null;
  }

  onShift(minute) {
    const agents = new Set();
    for (const agent of this.slots.keys()) if (this.at(agent, minute)) agents.add(agent);
    return agents;
  }
}
