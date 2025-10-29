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
    const { country, search, category, limit = 50 } = req.query;
    
    // Fetch channels data
    const channelsResponse = await fetch('https://iptv-org.github.io/api/channels.json');
    let channels = await channelsResponse.json();
    
    // Fetch streams data
    const streamsResponse = await fetch('https://iptv-org.github.io/api/streams.json');
    const streams = await streamsResponse.json();
    
    // Fetch logos data
    const logosResponse = await fetch('https://iptv-org.github.io/api/logos.json');
    const logos = await logosResponse.json();
    
    // Fetch countries data
    const countriesResponse = await fetch('https://iptv-org.github.io/api/countries.json');
    const countries = await countriesResponse.json();

    // Combine data
    const enrichedChannels = channels.map(channel => {
      // Find streams for this channel
      const channelStreams = streams.filter(stream => 
        stream.channel === channel.id || stream.feed === channel.id
      );
      
      // Find logo for this channel
      const channelLogo = logos.find(logo => 
        logo.channel === channel.id && !logo.feed
      ) || logos.find(logo => logo.channel === channel.id);
      
      // Find country info
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

    // Apply filters
    let filteredChannels = enrichedChannels;

    if (country) {
      filteredChannels = filteredChannels.filter(channel => 
        channel.country === country.toUpperCase()
      );
    }

    if (search) {
      const searchLower = search.toLowerCase();
      filteredChannels = filteredChannels.filter(channel =>
        channel.name.toLowerCase().includes(searchLower) ||
        channel.alt_names.some(alt => alt.toLowerCase().includes(searchLower))
      );
    }

    if (category) {
      filteredChannels = filteredChannels.filter(channel =>
        channel.categories.includes(category.toLowerCase())
      );
    }

    // Apply limit
    filteredChannels = filteredChannels.slice(0, parseInt(limit));

    res.json({
      success: true,
      data: filteredChannels,
      total: filteredChannels.length
    });

  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    });
  }
};
