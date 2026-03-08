"use strict";

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const z = require("zod");

const events = [
  {
    id: "evt-sf-founder-mixer",
    title: "sf founder mixer",
    city: "sf",
    venue: "mission district rooftop hall",
    date: "2026-04-19",
    tag: "networking",
    seats_available: 40,
  },
  {
    id: "evt-sf-demo-day-afterparty",
    title: "sf demo day afterparty",
    city: "sf",
    venue: "soma social club",
    date: "2026-04-20",
    tag: "afterparty",
    seats_available: 24,
  },
  {
    id: "evt-london-team-lodging",
    title: "london team lodging block",
    city: "london",
    venue: "old street suites",
    date: "2026-05-09",
    tag: "lodging",
    seats_available: 12,
  },
  {
    id: "evt-london-workshop-room-a",
    title: "london workshop room a",
    city: "london",
    venue: "canary wharf conference centre",
    date: "2026-06-13",
    tag: "workspace",
    seats_available: 16,
  },
];

const bookings = [];
const server = new McpServer({
  name: "event-booking-demo",
  version: "0.1.0",
});

function getEvent(eventId) {
  const event = events.find((item) => item.id === eventId);
  if (!event) {
    throw new Error(`event not found: ${eventId}`);
  }
  return event;
}

server.registerTool(
  "list_reservable_events",
  {
    description: "list reservable events, lodging, or workspaces by city and tag",
    inputSchema: {
      city: z.string().optional().describe("optional city filter"),
      tag: z.string().optional().describe("optional event tag filter"),
      min_seats: z.number().int().positive().optional().describe("optional minimum available seats"),
    },
  },
  async ({ city, tag, min_seats = 1 }) => {
    const filtered = events.filter((event) => {
      if (city && event.city !== String(city).toLowerCase()) {
        return false;
      }
      if (tag && event.tag !== String(tag).toLowerCase()) {
        return false;
      }
      if (event.seats_available < min_seats) {
        return false;
      }
      return true;
    });

    return {
      content: [{ type: "text", text: JSON.stringify({ events: filtered }, null, 2) }],
    };
  }
);

server.registerTool(
  "get_event_details",
  {
    description: "get detailed information for a reservable event",
    inputSchema: {
      event_id: z.string().describe("the event identifier"),
    },
  },
  async ({ event_id }) => {
    return {
      content: [{ type: "text", text: JSON.stringify({ event: getEvent(event_id) }, null, 2) }],
    };
  }
);

server.registerTool(
  "create_reservation",
  {
    description: "create a reservation against an event, lodging block, or workspace",
    inputSchema: {
      event_id: z.string().describe("the event identifier"),
      attendee_name: z.string().describe("the attendee or team contact"),
      seats: z.number().int().positive().describe("number of seats to reserve"),
      note: z.string().optional().describe("optional note for the reservation"),
    },
  },
  async ({ event_id, attendee_name, seats, note = "" }) => {
    const event = getEvent(event_id);
    if (event.seats_available < seats) {
      throw new Error(`only ${event.seats_available} seats remain for ${event.title}`);
    }

    event.seats_available -= seats;
    const booking = {
      reservation_id: `booking-${bookings.length + 1}`,
      event_id,
      attendee_name,
      seats,
      note,
      venue: event.venue,
      city: event.city,
      status: "confirmed",
    };
    bookings.push(booking);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              booking,
              seats_remaining: event.seats_available,
            },
            null,
            2
          ),
        },
      ],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
