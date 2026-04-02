# Streamlit Dashboard

Launch the dashboard from the repository root:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The dashboard imports the simulator directly through `run_sim.simulate()` and does not shell out to the CLI.
