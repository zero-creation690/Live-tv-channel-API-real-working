// Main API endpoint with documentation
// Created by https://t.me/zerodevbro

module.exports = async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const baseUrl = `https://${req.headers.host}`;

  res.status(200).json({
    success: true,
    name: "IPTV Search API",
    version: "1.0.0",
    description: "Search and filter IPTV channels with streams, logos, and metadata",
    creator: "https://t.me/zerodevbro",
    timestamp: new Date().toISOString(),
    endpoints: {
      search: {
        path: "/api/search",
        method: "GET",
        description: "Advanced search with multiple filters",
        parameters: {
          q: {
            type: "string",
            required: false,
            description: "Search query (channel name, network, owners)"
          },
          country: {
            type: "string",
            required: false,
            description: "Filter by country code (e.g., US, UK, CA)",
            example: "US"
          },
          category: {
            type: "string",
            required: false,
            description: "Filter by category",
            example: "news"
          },
          nsfw: {
            type: "boolean",
            required: false,
            description: "Filter NSFW content (true/false)"
          },
          hasStreams: {
            type: "boolean",
            required: false,
            description: "Only show channels with streams (true/false)"
          },
          limit: {
            type: "integer",
            required: false,
            default: 50,
            description: "Number of results per page"
          },
          offset: {
            type: "integer",
            required: false,
            default: 0,
            description: "Pagination offset"
          }
        },
        examples: [
          `${baseUrl}/api/search?q=BBC&country=UK`,
          `${baseUrl}/api/search?country=US&category=news&hasStreams=true`,
          `${baseUrl}/api/search?q=sport&limit=20`
        ]
      },
      channels: {
        path: "/api/channels",
        method: "GET",
        description: "Get channels with optional filters",
        parameters: {
          search: {
            type: "string",
            required: false,
            description: "Search channel name or network"
          },
          country: {
            type: "string",
            required: false,
            description: "Filter by country code"
          }
        },
        examples: [
          `${baseUrl}/api/channels?country=US`,
          `${baseUrl}/api/channels?search=news`,
          `${baseUrl}/api/channels?search=BBC&country=UK`
        ]
      },
      countries: {
        path: "/api/countries",
        method: "GET",
        description: "Get all countries with channel counts",
        parameters: {
          code: {
            type: "string",
            required: false,
            description: "Get specific country by code"
          },
          includeChannels: {
            type: "boolean",
            required: false,
            description: "Include full channel data (true/false)"
          }
        },
        examples: [
          `${baseUrl}/api/countries`,
          `${baseUrl}/api/countries?code=US`,
          `${baseUrl}/api/countries?code=UK&includeChannels=true`
        ]
      },
      categories: {
        path: "/api/categories",
        method: "GET",
        description: "Get all available categories",
        examples: [
          `${baseUrl}/api/categories`
        ]
      }
    },
    responseFormat: {
      success: "boolean - Request status",
      timestamp: "string - ISO 8601 timestamp",
      count: "integer - Number of results",
      query: "object - Applied filters",
      creator: "string - API creator",
      data: "array - Results array"
    },
    cors: {
      enabled: true,
      allowedOrigins: "*",
      allowedMethods: ["GET", "POST", "OPTIONS"]
    },
    dataSources: {
      channels: "https://github.com/iptv-org/database",
      streams: "https://github.com/iptv-org/iptv",
      updated: "Real-time from iptv-org"
    },
    contact: {
      telegram: "https://t.me/zerodevbro",
      github: "https://github.com/iptv-org/api"
    }
  });
};
