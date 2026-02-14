// API client for blast-campaigns-api
// Using the real blast-campaigns-api endpoint

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://blast-campaigns-api.blastjunior.com';

/**
 * Fetch all campaigns from the blast-campaigns-api
 * @returns {Promise<Array>} Array of campaign objects
 */
export async function fetchCampaigns() {
  try {
    const response = await fetch(`${API_BASE_URL}/campaigns`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch campaigns:', error);
    throw error;
  }
}

/**
 * Create a new campaign
 * @param {Object} campaignData - Campaign data to create
 * @returns {Promise<Object>} Created campaign object
 */
export async function createCampaign(campaignData) {
  try {
    const response = await fetch(`${API_BASE_URL}/campaigns`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(campaignData),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Failed to create campaign:', error);
    throw error;
  }
}

/**
 * Update an existing campaign
 * @param {number} id - Campaign ID to update
 * @param {Object} campaignData - Updated campaign data
 * @returns {Promise<Object>} Updated campaign object
 */
export async function updateCampaign(id, campaignData) {
  try {
    const response = await fetch(`${API_BASE_URL}/campaigns/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(campaignData),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Failed to update campaign:', error);
    throw error;
  }
}

/**
 * Delete a campaign
 * @param {number} id - Campaign ID to delete
 * @returns {Promise<boolean>} Success status
 */
export async function deleteCampaign(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/campaigns/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return true;
  } catch (error) {
    console.error('Failed to delete campaign:', error);
    throw error;
  }
}