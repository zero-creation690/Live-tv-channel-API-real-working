// API endpoint for channel search
// Created by https://t.me/zerodevbro

const channels = require('../data/channels.json');
const streams = require('../data/streams.json');
const logos = require('../data/logos.json');

module.exports = async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { search, country } = req.query;

  try {
    let results = channels.map(channel => {
      const channelStreams = streams.filter(s => s.channel === channel.id);
      const channelLogos = logos.filter(l => l.channel === channel.id);
      
      return {
        id: channel.id,
        name: channel.name,
        alternativeNames: channel.alt_names || [],
        network: channel.network || null,
        owners: channel.owners || [],
        country: channel.country || null,
        categories: channel.categories || [],
        isNsfw: channel.is_nsfw || false,
        launched: channel.launched || null,
        closed: channel.closed || null,
        replacedBy: channel.replaced_by || null,
        website: channel.website || null,
        streams: channelStreams.map(stream => ({
          title: stream.title || null,
          url: stream.url,
          quality: stream.quality || null,
          referrer: stream.referrer || null,
          userAgent: stream.user_agent || null
        })),
        logos: channelLogos.map(logo => ({
          url: logo.url,
          width: logo.width,
          height: logo.height,
          format: logo.format || null,
          tags: logo.tags || []
        }))
      };
    });

    // Filter by country
    if (country) {
      results = results.filter(c => 
        c.country?.toLowerCase() === country.toLowerCase()
      );
    }

    // Filter by search query
    if (search) {
      const searchLower = search.toLowerCase();
      results = results.filter(c => 
        c.name?.toLowerCase().includes(searchLower) ||
        c.alternativeNames?.some(name => name.toLowerCase().includes(searchLower)) ||
        c.network?.toLowerCase().includes(searchLower)
      );
    }

    res.status(200).json({
      success: true,
      timestamp: new Date().toISOString(),
      count: results.length,
      query: {
        search: search || null,
        country: country || null
      },
      creator: "https://t.me/zerodevbro",
      data: results
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      timestamp: new Date().toISOString(),
      error: {
        message: error.message,
        code: "INTERNAL_ERROR"
      },
      creator: "https://t.me/zerodevbro"
    });
  }
};
