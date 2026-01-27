const fs = require('fs');
const path = require('path');
const os = require('os');

const configPath = path.join(os.homedir(), '.clawdbot/clawdbot.json');
try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

    // Ensure structure exists
    config.agents = config.agents || {};
    config.agents.defaults = config.agents.defaults || {};

    // Update the workspace to Projects folder
    config.agents.defaults.workspace = "/Users/mattkuo/Projects";

    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    console.log("Configuration updated successfully with workspace ~/Projects.");
} catch (e) {
    console.error("Error updating config:", e);
    process.exit(1);
}
