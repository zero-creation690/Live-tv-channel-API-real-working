// API endpoint for categories
// Created by https://t.me/zerodevbro

const channels = require('../data/channels.json');

module.exports = async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    // Extract all unique categories
    const categoryMap = new Map();

    channels.forEach(channel => {
      if (channel.categories && Array.isArray(channel.categories)) {
        channel.categories.forEach(category => {
          if (!categoryMap.has(category)) {
            categoryMap.set(category, {
              name: category,
              channelCount: 0,
              channels: []
            });
          }
          
          const cat = categoryMap.get(category);
          cat.channelCount++;
          cat.channels.push({
            id: channel.id,
            name: channel.name,
            country: channel.country
          });
        });
      }
    });

    // Convert to array and sort by channel count
    const categoriesData = Array.from(categoryMap.values())
      .sort((a, b) => b.channelCount - a.channelCount)
      .map(cat => ({
        name: cat.name,
        displayName: cat.name.charAt(0).toUpperCase() + cat.name.slice(1),
        channelCount: cat.channelCount,
        topChannels: cat.channels.slice(0, 5) // Only show top 5 channels
      }));

    res.status(200).json({
      success: true,
      timestamp: new Date().toISOString(),
      count: categoriesData.length,
      totalChannels: channels.length,
      creator: "https://t.me/zerodevbro",
      data: categoriesData
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
