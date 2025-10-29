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
    const { q, country, category, limit = 20 } = req.query;
    
    if (!q) {
      return res.status(400).json({
        success: false,
        error: 'Search query (q) is required'
      });
    }

    // Fetch all data
    const [channelsResponse, streamsResponse, logosResponse, countriesResponse] = await Promise.all([
      fetch('https://iptv-org.github.io/api/channels.json'),
      fetch('https://iptv-org.github.io/api/streams.json'),
      fetch('https://iptv-org.github.io/api/logos.json'),
      fetch('https://iptv-org.github.io/api/countries.json')
    ]);

    const channels = await channelsResponse.json();
    const streams = await streamsResponse.json();
    const logos = await logosResponse.json();
    const countries = await countriesResponse.json();

    const searchTerm = q.toLowerCase();
    
    // Search channels
    let results = channels.filter(channel => {
      const nameMatch = channel.name.toLowerCase().includes(searchTerm);
      const altMatch = channel.alt_names && channel.alt_names.some(alt => 
        alt.toLowerCase().includes(searchTerm)
      );
      
      return nameMatch || altMatch;
    });

    // Apply country filter
    if (country) {
      results = results.filter(channel => channel.country === country.toUpperCase());
    }

    // Apply category filter
    if (category) {
      results = results.filter(channel => 
        channel.categories.includes(category.toLowerCase())
      );
    }

    // Enrich results with additional data
    const enrichedResults = results.slice(0, parseInt(limit)).map(channel => {
      const channelStreams = streams.filter(stream => 
        stream.channel === channel.id || stream.feed === channel.id
      );
      
      const channelLogo = logos.find(logo => 
        logo.channel === channel.id && !logo.feed
      ) || logos.find(logo => logo.channel === channel.id);
      
      const countryInfo = countries.find(c => c.code === channel.country);
      
      return {
        id: channel.id,
        name: channel.name,
        alt_names: channel.alt_names,
        country: channel.country,
        country_name: countryInfo ? countryInfo.name : null,
        country_flag: countryInfo ? countryInfo.flag : null,
        categories: channel.categories,
        network: channel.network,
        website: channel.website,
        is_nsfw: channel.is_nsfw,
        logo: channelLogo ? channelLogo.url : null,
        streams: channelStreams.map(stream => ({
          url: stream.url,
          quality: stream.quality,
          title: stream.title,
          referrer: stream.referrer
        }))
      };
    });

    res.json({
      success: true,
      query: q,
      data: enrichedResults,
      total: enrichedResults.length
    });

  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
};
