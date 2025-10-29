// API endpoint for countries list with channels
// Created by https://t.me/zerodevbro

const channels = require('../data/channels.json');
const countries = require('../data/countries.json');
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

  const { code, includeChannels } = req.query;

  try {
    let countriesData = countries.map(country => {
      const countryChannels = channels.filter(c => c.country === country.code);
      const channelCount = countryChannels.length;

      let result = {
        name: country.name,
        code: country.code,
        flag: country.flag,
        languages: country.languages || [],
        channelCount: channelCount
      };

      // Include full channel data if requested
      if (includeChannels === 'true' || code === country.code) {
        result.channels = countryChannels.map(channel => {
          const channelStreams = streams.filter(s => s.channel === channel.id);
          const channelLogos = logos.filter(l => l.channel === channel.id);
          
          return {
            id: channel.id,
            name: channel.name,
            alternativeNames: channel.alt_names || [],
            network: channel.network || null,
            categories: channel.categories || [],
            isNsfw: channel.is_nsfw || false,
            website: channel.website || null,
            streams: channelStreams.map(stream => ({
              title: stream.title || null,
              url: stream.url,
              quality: stream.quality || null
            })),
            logos: channelLogos.map(logo => ({
              url: logo.url,
              width: logo.width,
              height: logo.height,
              format: logo.format || null
            }))
          };
        });
      }

      return result;
    });

    // Filter by country code if specified
    if (code) {
      countriesData = countriesData.filter(c => 
        c.code.toLowerCase() === code.toLowerCase()
      );
    }

    // Only show countries with channels
    countriesData = countriesData.filter(c => c.channelCount > 0);

    // Sort by channel count
    countriesData.sort((a, b) => b.channelCount - a.channelCount);

    res.status(200).json({
      success: true,
      timestamp: new Date().toISOString(),
      count: countriesData.length,
      totalChannels: countriesData.reduce((sum, c) => sum + c.channelCount, 0),
      query: {
        code: code || null,
        includeChannels: includeChannels === 'true'
      },
      creator: "https://t.me/zerodevbro",
      data: countriesData
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
