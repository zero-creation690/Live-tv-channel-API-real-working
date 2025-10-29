const fetch = require('node-fetch');

module.exports = async (req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  try {
    const channelsResponse = await fetch('https://iptv-org.github.io/api/channels.json');
    const channels = await channelsResponse.json();
    
    const countriesResponse = await fetch('https://iptv-org.github.io/api/countries.json');
    const countries = await countriesResponse.json();

    // Count channels per country
    const countryCounts = channels.reduce((acc, channel) => {
      if (channel.country) {
        acc[channel.country] = (acc[channel.country] || 0) + 1;
      }
      return acc;
    }, {});

    // Enrich countries with channel counts
    const countriesWithCounts = countries
      .filter(country => countryCounts[country.code])
      .map(country => ({
        code: country.code,
        name: country.name,
        flag: country.flag,
        channel_count: countryCounts[country.code] || 0,
        languages: country.languages
      }))
      .sort((a, b) => b.channel_count - a.channel_count);

    res.json({
      success: true,
      data: countriesWithCounts,
      total: countriesWithCounts.length
    });

  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
};
