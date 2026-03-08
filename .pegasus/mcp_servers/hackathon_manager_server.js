"use strict";

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const z = require("zod");

const hackathons = [
  {
    id: "hk-sf-ai-sprint",
    name: "sf ai sprint",
    city: "sf",
    venue: "mission bay builder hub",
    start_date: "2026-04-18",
    end_date: "2026-04-20",
    skill_track: "ai",
    slots_remaining: 18,
    max_team_size: 5,
  },
  {
    id: "hk-london-govtech-build",
    name: "london govtech build",
    city: "london",
    venue: "shoreditch civic lab",
    start_date: "2026-05-09",
    end_date: "2026-05-11",
    skill_track: "civic-tech",
    slots_remaining: 10,
    max_team_size: 4,
  },
  {
    id: "hk-sf-fintech-jam",
    name: "sf fintech jam",
    city: "sf",
    venue: "soma founders garage",
    start_date: "2026-06-13",
    end_date: "2026-06-14",
    skill_track: "fintech",
    slots_remaining: 22,
    max_team_size: 6,
  },
];

const reservations = [];
const server = new McpServer({
  name: "hackathon-manager-demo",
  version: "0.1.0",
});

function getHackathon(hackathonId) {
  const hackathon = hackathons.find((item) => item.id === hackathonId);
  if (!hackathon) {
    throw new Error(`hackathon not found: ${hackathonId}`);
  }
  return hackathon;
}

server.registerTool(
  "list_hackathons",
  {
    description: "list available hackathons and optionally filter by city or track",
    inputSchema: {
      city: z.string().optional().describe("optional city filter"),
      skill_track: z.string().optional().describe("optional skill track filter"),
      open_only: z.boolean().optional().describe("when true only include hackathons with slots remaining"),
    },
  },
  async ({ city, skill_track, open_only = true }) => {
    const filtered = hackathons.filter((hackathon) => {
      if (city && hackathon.city !== String(city).toLowerCase()) {
        return false;
      }
      if (skill_track && hackathon.skill_track !== String(skill_track).toLowerCase()) {
        return false;
      }
      if (open_only && hackathon.slots_remaining <= 0) {
        return false;
      }
      return true;
    });

    return {
      content: [{ type: "text", text: JSON.stringify({ hackathons: filtered }, null, 2) }],
    };
  }
);

server.registerTool(
  "get_hackathon_details",
  {
    description: "get full details for a single hackathon",
    inputSchema: {
      hackathon_id: z.string().describe("the hackathon identifier"),
    },
  },
  async ({ hackathon_id }) => {
    return {
      content: [{ type: "text", text: JSON.stringify({ hackathon: getHackathon(hackathon_id) }, null, 2) }],
    };
  }
);

server.registerTool(
  "reserve_team_slot",
  {
    description: "reserve a team slot for a hackathon",
    inputSchema: {
      hackathon_id: z.string().describe("the hackathon identifier"),
      team_name: z.string().describe("the team name"),
      team_size: z.number().int().positive().describe("the number of team members"),
      contact_email: z.string().describe("team contact email"),
    },
  },
  async ({ hackathon_id, team_name, team_size, contact_email }) => {
    const hackathon = getHackathon(hackathon_id);
    if (team_size > hackathon.max_team_size) {
      throw new Error(`team size exceeds max team size of ${hackathon.max_team_size}`);
    }
    if (hackathon.slots_remaining <= 0) {
      throw new Error("no slots remaining for this hackathon");
    }

    hackathon.slots_remaining -= 1;
    const reservation = {
      reservation_id: `team-${reservations.length + 1}`,
      hackathon_id,
      team_name,
      team_size,
      contact_email,
      city: hackathon.city,
      venue: hackathon.venue,
      status: "reserved",
    };
    reservations.push(reservation);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              reservation,
              slots_remaining: hackathon.slots_remaining,
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
