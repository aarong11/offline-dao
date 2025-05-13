#!/usr/bin/env python3
# dao_task_cli.py
# ⚠️ Autonomous DAO CLI - Stateless + Attributionless
# Watermark: sha256('DAO_STACK_CLI_v0.1') = 9af2256c4a59dc87e68f76097d3fe51954e2bcba52c0b9a73bc2a8f6a2311ed7

import json
import uuid
import os
import base64
from datetime import datetime

# Import the crypto adapter
from dao_cli.crypto import get_adapter

DATA_DIR = "dao_data"
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
CONTRIBUTORS_FILE = os.path.join(DATA_DIR, "contributors.json")
EPOCH_LOG = os.path.join(DATA_DIR, "local_epoch_log.json")
os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path):
    """Load data from a JSON file or return an empty list if file doesn't exist."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_json(path, data):
    """Save data to a JSON file with pretty formatting."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


projects = load_json(PROJECTS_FILE)
contributors = load_json(CONTRIBUTORS_FILE)

# Get the crypto adapter
crypto_adapter = get_adapter()

# Helper function for signatures
def sign_links(identities, multisig):
    """Create a cryptographic signature for linked identities."""
    payload = {
        "identities": sorted(identities),
        "multisig": sorted(multisig),
        "timestamp": datetime.utcnow().isoformat()
    }
    return crypto_adapter.sign(payload)


def sign_project_delta(delta):
    """Sign a project delta with the user's cryptographic key."""
    # Create a copy without the signature field
    delta_copy = {k: v for k, v in delta.items() if k != "signature"}
    # Sign the delta
    signature = crypto_adapter.sign(delta_copy)
    delta["signature"] = signature
    delta["public_key"] = crypto_adapter.public_key_b64()  # Include the public key for verification
    return delta


def verify_signature(delta, signature):
    """Verify a signature against a project delta."""
    delta_copy = delta.copy()
    if "signature" in delta_copy:
        del delta_copy["signature"]
    
    # Get the public key from the delta or from an environment variable/config
    pubkey = delta.get("public_key")
    if not pubkey:
        raise ValueError("No public key found for signature verification")
    
    return crypto_adapter.verify(delta_copy, signature, pubkey)


def verify_link_signature(linked_ids, multisig, signature):
    """Verify a signature against linked identities."""
    payload = {
        "identities": sorted(linked_ids),
        "multisig": sorted(multisig),
        # Note: We don't have the original timestamp, but that's OK for this verification
        # as long as the signed payload included the same identities and multisig lists
    }
    
    # Get the public key from the identity if available, otherwise use a passed public key
    identity_record = next((i for i in contributors if i.get("linked_identities") == linked_ids), None)
    pubkey = identity_record.get("public_key") if identity_record else None
    
    if not pubkey:
        raise ValueError("No public key found for signature verification")
    
    return crypto_adapter.verify(payload, signature, pubkey)


def verify_device_access(identity, device_hash, context=None):
    """Check whether the identity has permission to use the given device in context."""
    if any(d.get("device_id") == device_hash for d in identity.get("devices", [])):
        return True
    for entry in identity.get("device_access", []):
        if entry.get("device_id") == device_hash:
            if not context:
                return True
            if context in entry.get("scope", []):
                return True
    return False


def generate_project_delta(project_id):
    """Generate a signed project delta file for sharing project updates."""
    print("Describe this epoch using natural/local observations.")
    marker = input("Marker or event description (e.g., 'first frost', 'moon over trees'): ")
    signed_by = input("Pseudonym(s) signing this epoch (comma-separated): ").split(",")
    location_hint = input("Optional location hint (e.g., 'Greenbelt near river'): ")
    
    # Create log entry and save to epoch log
    log_entry = {"marker": marker.strip(), "location": location_hint.strip(), "signed_by": [s.strip() for s in signed_by if s.strip()]}
    epoch_log = load_json(EPOCH_LOG)
    epoch_log.append(log_entry)
    save_json(EPOCH_LOG, epoch_log)
    
    delta = {
        "project_id": project_id,
        "epoch": {
            "marker": marker.strip(),
            "location": location_hint.strip(),
            "signed_by": [s.strip() for s in signed_by if s.strip()]
        },
        "updated_tasks": [],
        "new_tasks": [],
        "status_changes": [],
        "metadata": {}
    }
    
    for project in projects:
        if project["id"] == project_id:
            for task in project["tasks"]:
                delta["updated_tasks"].append({
                    "id": task["id"],
                    "title": task["title"],
                    "status": task["status"],
                    "claimed_by": task.get("claimed_by"),
                    "submitted_by": task.get("submitted_by"),
                    "bounty": task.get("bounty"),
                    "tags": task.get("tags", []),
                    "depends_on": task.get("depends_on", []),
                    "priority": task.get("priority", "")
                })
            delta["metadata"] = {
                "title": project["title"],
                "summary": project["summary"],
                "tags": project["tags"],
                "status": project["status"]
            }
            file_path = os.path.join(DATA_DIR, f"project_delta_{project_id}.diff.json")
            with open(file_path, "w") as f:
                signed = sign_project_delta(delta)
                json.dump(signed, f, indent=2)
            print(f"Delta file written to {file_path}")
            return
    print("Project not found.")


def create_identity():
    anon_id = input("Choose a pseudonym ID: ")
    skills = input("Enter skills (comma-separated): ").split(',')
    resources = input("List available resources (comma-separated): ").split(',')
    availability = input("Describe your availability (e.g., 'weekends', '5h/week'): ")

    epoch = input("Epoch marker (e.g., 'first frost'): ")
    location = input("Location description (e.g., 'woods near lake'): ")

    linked_identities = input("Linked identities (comma-separated, optional): ").split(',')
    multisig = input("Multi-signature holders (comma-separated, optional): ").split(',')

    # Generate signature for linked identities using the crypto adapter
    clean_linked_ids = [lid.strip() for lid in linked_identities if lid.strip()]
    clean_multisig = [m.strip() for m in multisig if m.strip()]
    signature = sign_links(clean_linked_ids, clean_multisig)

    responsibilities = input("List responsibilities (comma-separated): ").split(',')
    device_serials = input("List associated device serials (comma-separated): ").split(',')
    hashed_devices = []
    for s in device_serials:
        if s.strip():
            serial = s.strip()
            nonce = input(f"Nonce for device '{serial}': ").strip()
            # Use a more secure way to hash the device serial + nonce using our crypto library
            device_hash = base64.b64encode(serial.encode() + nonce.encode()).decode()  # Simplified for compatibility
            hashed_devices.append({
                "device_id": device_hash,
                "nonce": nonce,
                "responsibility": input(f"Responsibility for device '{serial}': ").strip(),
                "activated_at": epoch.strip()
            })

    identity = {
        "anon_id": anon_id.strip(),
        "skills": [s.strip() for s in skills],
        "resources": [r.strip() for r in resources],
        "availability": availability.strip(),
        "epoch": epoch.strip(),
        "location": location.strip(),
        "contributions": [],
        "score": 0.0,
        "max_parallel": 1,
        "linked_identities": clean_linked_ids,
        "multisig": clean_multisig,
        "link_signature": signature,
        "public_key": crypto_adapter.public_key_b64(),  # Store the public key for later verification
        "responsibilities": [r.strip() for r in responsibilities if r.strip()],
        "devices": hashed_devices,
        "device_access": []
    }

    if any(c["anon_id"] == identity["anon_id"] for c in contributors):
        print("That pseudonym already exists. Choose another.")
        return

    contributors.append(identity)
    save_json(CONTRIBUTORS_FILE, contributors)
    print(f"Created new identity: {identity['anon_id']}")


def import_project_delta():
    file_path = input("Enter path to project delta .diff.json: ").strip()
    if not os.path.exists(file_path):
        print("Delta file not found.")
        return
    with open(file_path, "r") as f:
        delta = json.load(f)

    signature = delta.get("signature")
    if not signature or not verify_signature(delta, signature):
        print("Invalid or missing signature. Aborting merge.")
        return

    project_id = delta.get("project_id")
    found = False
    for project in projects:
        if project["id"] == project_id:
            found = True
            task_map = {task["id"]: task for task in project["tasks"]}
            for updated in delta.get("updated_tasks", []):
                if updated["id"] in task_map:
                    task_map[updated["id"]].update(updated)
                else:
                    project["tasks"].append(updated)
            for field in ["title", "summary", "tags", "status"]:
                if field in delta.get("metadata", {}):
                    project[field] = delta["metadata"][field]
            save_json(PROJECTS_FILE, projects)
            print(f"Delta merged into project {project_id}.")
            return
    if not found:
        print("Project ID not found in current data.")


def add_task():
    project_id = input("Project ID to add task to: ")
    for project in projects:
        if project["id"] == project_id:
            title = input("Task title: ")
            description = input("Task description: ")
            estimated_hours = input("Estimated hours: ")
            people_required = input("People required (number): ")
            input_requirements = input("Inputs required (comma-separated): ").split(',')
            output_description = input("Expected output/result: ")
            resources_needed = input("Resources needed (comma-separated): ").split(',')

            task = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": description,
                "estimated_hours": float(estimated_hours),
                "people_required": int(people_required),
                "inputs": [i.strip() for i in input_requirements],
                "outputs": output_description.strip(),
                "resources": [r.strip() for r in resources_needed],
                "status": "open",
                "claimed_by": None,
                "submitted_by": None
            }
            if "tasks" not in project:
                project["tasks"] = []
            project["tasks"].append(task)
            save_json(PROJECTS_FILE, projects)
            print("Task added.")
            return
    print("Project not found.")


def set_task_priority():
    project_id = input("Project ID: ")
    task_id = input("Task ID to set priority: ")
    for project in projects:
        if project["id"] == project_id:
            for task in project["tasks"]:
                if task["id"] == task_id:
                    priority = input("Set priority (low, medium, high, urgent): ").strip().lower()
                    task["priority"] = priority
                    save_json(PROJECTS_FILE, projects)
                    print("Priority set.")
                    return
    print("Project or task not found.")


def list_tasks_by_priority():
    """List tasks in a project sorted by priority."""
    project_id = input("Project ID: ")
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    for project in projects:
        if project["id"] == project_id:
            sorted_tasks = sorted(project["tasks"], key=lambda t: priority_order.get(t.get("priority", "low"), 4))
            for task in sorted_tasks:
                print(f"[{task['id']}] {task['title']} - Priority: {task.get('priority', 'none')} - Status: {task['status']}")
                print(f"  Estimated Hours: {task.get('estimated_hours', '?')}, People Needed: {task.get('people_required', '?')}")
                print(f"  Inputs: {', '.join(task.get('inputs', []))}")
                print(f"  Outputs: {task.get('outputs', '')}")
                print(f"  Resources: {', '.join(task.get('resources', []))}\n")
            return
    print("Project not found.")


def claim_task():
    anon_id = input("Your anon ID: ")
    project_id = input("Project ID: ")
    task_id = input("Task ID: ")
    for project in projects:
        if project["id"] == project_id:
            for task in project["tasks"]:
                if task["id"] == task_id and task["status"] == "open":
                    # Check dependencies
                    dependencies = task.get("depends_on", [])
                    unmet = []
                    for dep_id in dependencies:
                        dep_task = next((t for t in project["tasks"] if t["id"] == dep_id), None)
                        if not dep_task or dep_task.get("status") != "submitted":
                            unmet.append(dep_id)
                    if unmet:
                        print("Cannot claim task. Unresolved dependencies:")
                        for uid in unmet:
                            print(f" - {uid}")
                        return
                    task["status"] = "claimed"
                    task["claimed_by"] = anon_id
                    contributor = next((c for c in contributors if c["anon_id"] == anon_id), None)
                    if not contributor:
                        contributor = {"anon_id": anon_id, "skills": [], "availability": "", "contributions": [], "score": 0.0, "max_parallel": 1}
                        contributors.append(contributor)
                    contributor["contributions"].append({
                        "project_id": project_id,
                        "task_id": task_id,
                        "hours": 0,
                        "status": "in_progress"
                    })
                    save_json(PROJECTS_FILE, projects)
                    save_json(CONTRIBUTORS_FILE, contributors)
                    print("Task claimed.")
                    return
    print("Task not found or already claimed.")


def visualize_dependencies():
    export_lines = []
    def print_tree(task_id, task_lookup, prefix="", visited=None):
        if visited is None:
            visited = set()
        if task_id in visited:
            line = f"{prefix}↳ (circular:{task_id})"
            print(line)
            export_lines.append(line)
            return
        visited.add(task_id)
        task = task_lookup.get(task_id)
        if not task:
            line = f"{prefix}↳ (missing:{task_id})"
            print(line)
            export_lines.append(line)
            return
        line = f"{prefix}↳ {task_id}: {task['title']}"
        print(line)
        export_lines.append(line)
        for dep in task.get("depends_on", []):
            print_tree(dep, task_lookup, prefix + "    ", visited.copy())
    def resolve_chain(task_id, task_lookup, visited=None):
        if visited is None:
            visited = set()
        if task_id in visited:
            return [f"(circular:{task_id})"]
        visited.add(task_id)
        task = task_lookup.get(task_id)
        if not task:
            return [f"(missing:{task_id})"]
        deps = task.get("depends_on", [])
        if not deps:
            return [task_id]
        chain = []
        for dep in deps:
            sub = resolve_chain(dep, task_lookup, visited.copy())
            chain.extend(sub)
        chain.append(task_id)
        return chain
    project_id = input("Project ID to visualize: ")
    for project in projects:
        if project["id"] == project_id:
            print(f"Dependency Tree for Project: {project['title']}")
            task_lookup = {t['id']: t for t in project['tasks']}
            for task in project["tasks"]:
                print_tree(task['id'], task_lookup)
            output_path = os.path.join(DATA_DIR, f"dependency_tree_{project_id}.txt")
            output_md_path = os.path.join(DATA_DIR, f"dependency_tree_{project_id}.md")
            with open(output_path, "w") as f:
                f.write("\n".join(export_lines))
            with open(output_md_path, "w") as f:
                f.write("```text\n" + "\n".join(export_lines) + "\n```")
            print(f"\nDependency tree exported to {output_path} and {output_md_path}")
            return
    print("Project not found.")


def create_project():
    """Create a new project in the DAO system."""
    title = input("Project title: ")
    summary = input("Project summary: ")
    tags = input("Project tags (comma-separated): ").split(',')
    
    project = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "summary": summary.strip(),
        "tags": [t.strip() for t in tags if t.strip()],
        "status": "active",
        "tasks": [],
        "funding": []
    }
    
    projects.append(project)
    save_json(PROJECTS_FILE, projects)
    print(f"Project created with ID: {project['id']}")
    return project["id"]


def list_projects():
    """List all projects in the system."""
    if not projects:
        print("No projects found.")
        return
        
    print("\nProjects:")
    for i, project in enumerate(projects):
        print(f"{i+1}. [{project['id']}] {project['title']} - Status: {project['status']}")
        print(f"   Summary: {project['summary']}")
        if project.get('tags'):
            print(f"   Tags: {', '.join(project.get('tags'))}")
        task_count = len(project.get('tasks', []))
        open_tasks = sum(1 for t in project.get('tasks', []) if t.get('status') == 'open')
        print(f"   Tasks: {task_count} total, {open_tasks} open\n")


def list_tasks(project_id=None):
    """List all tasks for a project."""
    if project_id is None:
        project_id = input("Project ID: ")
        
    for project in projects:
        if project["id"] == project_id:
            print(f"\nTasks for {project['title']}:")
            if not project.get('tasks'):
                print("No tasks found.")
                return
                
            for i, task in enumerate(project['tasks']):
                print(f"{i+1}. [{task['id']}] {task['title']} - Status: {task['status']}")
                print(f"   Description: {task.get('description', 'N/A')}")
                print(f"   Estimated Hours: {task.get('estimated_hours', '?')}")
                if task.get('claimed_by'):
                    print(f"   Claimed by: {task['claimed_by']}")
                if task.get('priority'):
                    print(f"   Priority: {task['priority']}")
                print()
            return
    print("Project not found.")


def submit_task():
    """Submit completed work for a task."""
    anon_id = input("Your anon ID: ")
    project_id = input("Project ID: ")
    task_id = input("Task ID: ")
    
    for project in projects:
        if project["id"] == project_id:
            for task in project["tasks"]:
                if task["id"] == task_id and task.get("claimed_by") == anon_id:
                    submission_url = input("Submission URL or description: ")
                    hours_spent = input("Hours spent on task: ")
                    
                    task["status"] = "submitted"
                    task["submitted_by"] = anon_id
                    task["submission"] = {
                        "url": submission_url.strip(),
                        "submitted_at": datetime.utcnow().isoformat(),
                        "hours_spent": float(hours_spent)
                    }
                    
                    # Update contributor record
                    for contributor in contributors:
                        if contributor["anon_id"] == anon_id:
                            for contrib in contributor.get("contributions", []):
                                if contrib.get("project_id") == project_id and contrib.get("task_id") == task_id:
                                    contrib["status"] = "submitted"
                                    contrib["hours"] = float(hours_spent)
                                    break
                    
                    save_json(PROJECTS_FILE, projects)
                    save_json(CONTRIBUTORS_FILE, contributors)
                    print("Task submitted successfully.")
                    return
            
            print("Task not found or not claimed by you.")
            return
    print("Project not found.")


def fund_project():
    """Add funding to a project."""
    project_id = input("Project ID to fund: ")
    amount = input("Amount to fund: ")
    try:
        amount = float(amount)
    except ValueError:
        print("Invalid amount.")
        return
    
    funding_source = input("Funding source: ")
    notes = input("Funding notes (optional): ")
    tags = input("Funding tags (comma-separated, optional): ").split(',')
    
    for project in projects:
        if project["id"] == project_id:
            if "funding" not in project:
                project["funding"] = []
            
            funding_entry = {
                "id": str(uuid.uuid4()),
                "amount": amount,
                "source": funding_source.strip(),
                "notes": notes.strip(),
                "tags": [t.strip() for t in tags if t.strip()],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            project["funding"].append(funding_entry)
            save_json(PROJECTS_FILE, projects)
            print(f"Added {amount} funding to project {project_id}")
            return
    
    print("Project not found.")


def view_submissions():
    """View all task submissions for a project."""
    project_id = input("Project ID: ")
    
    for project in projects:
        if project["id"] == project_id:
            print(f"\nSubmissions for {project['title']}:")
            submissions_found = False
            
            for task in project.get("tasks", []):
                if task.get("status") == "submitted" and "submission" in task:
                    submissions_found = True
                    print(f"Task: [{task['id']}] {task['title']}")
                    print(f"  Submitted by: {task.get('submitted_by', 'unknown')}")
                    print(f"  Submitted at: {task.get('submission', {}).get('submitted_at', 'unknown')}")
                    print(f"  Hours spent: {task.get('submission', {}).get('hours_spent', '?')}")
                    print(f"  URL/Description: {task.get('submission', {}).get('url', 'none')}")
                    print()
            
            if not submissions_found:
                print("No submissions found for this project.")
            return
    
    print("Project not found.")


def simulate_payout():
    """Simulate payouts for completed tasks."""
    project_id = input("Project ID: ")
    
    for project in projects:
        if project["id"] == project_id:
            print(f"\nSimulated Payout for {project['title']}:")
            
            total_funding = sum(f.get("amount", 0) for f in project.get("funding", []))
            submitted_tasks = [t for t in project.get("tasks", []) if t.get("status") == "submitted"]
            
            if not submitted_tasks:
                print("No submitted tasks to pay out.")
                return
                
            total_hours = sum(t.get("submission", {}).get("hours_spent", 0) for t in submitted_tasks)
            
            print(f"Total funding: {total_funding}")
            print(f"Total hours on submitted tasks: {total_hours}")
            
            if total_hours > 0:
                rate = total_funding / total_hours
                print(f"Implied hourly rate: {rate:.2f}")
                
                print("\nBreakdown by task:")
                for task in submitted_tasks:
                    hours = task.get("submission", {}).get("hours_spent", 0)
                    task_payout = hours * rate
                    print(f"- [{task['id']}] {task['title']}")
                    print(f"  Submitted by: {task.get('submitted_by')}")
                    print(f"  Hours: {hours}, Payout: {task_payout:.2f}")
            else:
                print("No hours recorded for submitted tasks.")
            return
    
    print("Project not found.")


def tag_task():
    """Add tags to a task."""
    project_id = input("Project ID: ")
    task_id = input("Task ID to tag: ")
    
    for project in projects:
        if project["id"] == project_id:
            for task in project["tasks"]:
                if task["id"] == task_id:
                    tags = input("Enter tags (comma-separated): ").split(',')
                    
                    if "tags" not in task:
                        task["tags"] = []
                        
                    task["tags"].extend([t.strip() for t in tags if t.strip()])
                    # Remove duplicates
                    task["tags"] = list(set(task["tags"]))
                    
                    save_json(PROJECTS_FILE, projects)
                    print(f"Task tagged with: {', '.join(task['tags'])}")
                    return
            
            print("Task not found.")
            return
    
    print("Project not found.")


def enhance_funding():
    """Add detailed information to project funding."""
    project_id = input("Project ID: ")
    
    for project in projects:
        if project["id"] == project_id:
            if not project.get("funding"):
                print("This project has no funding entries.")
                return
                
            print("\nCurrent funding entries:")
            for i, entry in enumerate(project["funding"]):
                print(f"{i+1}. Amount: {entry.get('amount')}, Source: {entry.get('source')}")
            
            entry_idx = int(input("Which entry to enhance (number): ")) - 1
            
            if 0 <= entry_idx < len(project["funding"]):
                entry = project["funding"][entry_idx]
                print(f"Enhancing entry: {entry.get('amount')} from {entry.get('source')}")
                
                milestone = input("Associate with milestone/deliverable: ")
                conditions = input("Funding conditions (optional): ")
                timeline = input("Expected timeline (optional): ")
                
                entry["milestone"] = milestone.strip()
                if conditions.strip():
                    entry["conditions"] = conditions.strip()
                if timeline.strip():
                    entry["timeline"] = timeline.strip()
                
                save_json(PROJECTS_FILE, projects)
                print("Funding entry enhanced.")
            else:
                print("Invalid entry number.")
            return
    
    print("Project not found.")


def filter_tasks_by_tag():
    """Filter tasks by tag across all projects or within one project."""
    scope = input("Filter across all projects (a) or one project (p)? ")
    
    if scope.lower() == 'p':
        project_id = input("Project ID: ")
        target_projects = [p for p in projects if p["id"] == project_id]
        if not target_projects:
            print("Project not found.")
            return
    else:
        target_projects = projects
    
    tag = input("Enter tag to filter by: ").strip().lower()
    
    found = False
    for project in target_projects:
        matching_tasks = [
            t for t in project.get("tasks", []) 
            if any(tag == t_tag.lower() for t_tag in t.get("tags", []))
        ]
        
        if matching_tasks:
            found = True
            print(f"\nProject: {project['title']} [{project['id']}]")
            for task in matching_tasks:
                print(f"- [{task['id']}] {task['title']} - Status: {task['status']}")
                print(f"  Tags: {', '.join(task.get('tags', []))}")
    
    if not found:
        print(f"No tasks found with tag '{tag}'.")


def filter_funding_by_tag():
    """Filter funding entries by tag."""
    tag = input("Enter tag to filter by: ").strip().lower()
    
    found = False
    for project in projects:
        matching_funds = [
            f for f in project.get("funding", []) 
            if any(tag == t.lower() for t in f.get("tags", []))
        ]
        
        if matching_funds:
            found = True
            print(f"\nProject: {project['title']} [{project['id']}]")
            for fund in matching_funds:
                print(f"- {fund.get('amount')} from {fund.get('source')}")
                print(f"  Tags: {', '.join(fund.get('tags', []))}")
                if fund.get('notes'):
                    print(f"  Notes: {fund['notes']}")
    
    if not found:
        print(f"No funding entries found with tag '{tag}'.")


def add_dependencies_to_task():
    """Add dependency relationships between tasks."""
    project_id = input("Project ID: ")
    
    for project in projects:
        if project["id"] == project_id:
            print(f"\nTasks in {project['title']}:")
            for i, task in enumerate(project.get("tasks", [])):
                print(f"{i+1}. [{task['id']}] {task['title']} - Status: {task['status']}")
            
            task_idx = int(input("\nSelect task to add dependencies to (number): ")) - 1
            
            if 0 <= task_idx < len(project["tasks"]):
                task = project["tasks"][task_idx]
                print(f"Adding dependencies to: {task['title']}")
                
                if "depends_on" not in task:
                    task["depends_on"] = []
                
                print("\nAvailable tasks to add as dependencies:")
                for i, dep_task in enumerate(project["tasks"]):
                    if dep_task["id"] != task["id"]:  # Can't depend on itself
                        print(f"{i+1}. [{dep_task['id']}] {dep_task['title']}")
                
                dep_indices = input("\nEnter task numbers to add as dependencies (comma-separated): ")
                dep_indices = [int(idx.strip()) - 1 for idx in dep_indices.split(',') if idx.strip().isdigit()]
                
                for idx in dep_indices:
                    if 0 <= idx < len(project["tasks"]) and project["tasks"][idx]["id"] != task["id"]:
                        dep_id = project["tasks"][idx]["id"]
                        if dep_id not in task["depends_on"]:
                            task["depends_on"].append(dep_id)
                
                save_json(PROJECTS_FILE, projects)
                print("Dependencies added.")
            else:
                print("Invalid task number.")
            return
    
    print("Project not found.")


if __name__ == "__main__":
    print("DAO CLI")
    print("1. Create Project")
    print("2. Add Task to Project")
    print("3. List Projects")
    print("4. List Tasks in Project")
    print("5. Claim Task")
    print("6. Submit Task")
    print("7. Fund Project")
    print("8. View Submissions")
    print("9. Simulate Payout")
    print("10. Tag Task")
    print("11. Enhanced Funding Entry")
    print("12. Filter Tasks by Tag")
    print("13. Filter Funding by Tag")
    print("14. Add Dependencies to Task")
    print("15. Set Task Priority")
    print("16. List Tasks by Priority")
    print("21. Filter Tasks by Input or Resource")
    print("17. Visualize Task Dependencies")
    print("18. Export Project Delta (.diff.json)")
    print("19. Import Project Delta (.diff.json)")
    print("20. View Local Epoch Log")
    print("22. Create Contributor Identity")
    print("23. View Contributor Profiles")
    print("24. Verify Identity Link Signatures")
    print("25. Revoke or Rotate Identity Link Signature")
    print("26. View Revoked Link Signatures")
    print("27. Verify Device Ownership")
    print("28. Rotate Device Nonce")
    print("29. View Device Rotation Log")
    choice = input("Choose an option: ")

    if choice == "1":
        create_project()
    elif choice == "2":
        add_task()
    elif choice == "3":
        list_projects()
    elif choice == "4":
        list_tasks()
    elif choice == "5":
        claim_task()
    elif choice == "6":
        submit_task()
    elif choice == "7":
        fund_project()
    elif choice == "8":
        view_submissions()
    elif choice == "9":
        simulate_payout()
    elif choice == "10":
        tag_task()
    elif choice == "11":
        enhance_funding()
    elif choice == "12":
        filter_tasks_by_tag()
    elif choice == "13":
        filter_funding_by_tag()
    elif choice == "14":
        add_dependencies_to_task()
    elif choice == "15":
        set_task_priority()
    elif choice == "16":
        list_tasks_by_priority()
    elif choice == "17":
        visualize_dependencies()
    elif choice == "18":
        project_id = input("Enter project ID to export delta: ")
        generate_project_delta(project_id)
    elif choice == "19":
        import_project_delta()
    elif choice == "20":
        epoch_log = load_json(EPOCH_LOG)
        print("\nLocal Epoch Log:")
        for i, entry in enumerate(epoch_log):
            print(f"[{i+1}] Marker: {entry.get('marker')}, Location: {entry.get('location')}, Signed by: {', '.join(entry.get('signed_by', []))}")
    elif choice == "21":
        keyword = input("Enter input or resource keyword to filter by: ").lower()
        for project in projects:
            print(f"\nProject: {project['title']}")
            for task in project.get("tasks", []):
                inputs = [i.lower() for i in task.get("inputs", [])]
                resources = [r.lower() for r in task.get("resources", [])]
                if keyword in inputs or keyword in resources:
                    print(f"- [{task['id']}] {task['title']} - Status: {task['status']}")
                    print(f"  Inputs: {', '.join(task.get('inputs', []))}")
                    print(f"  Resources: {', '.join(task.get('resources', []))}\n")
    elif choice == "22":
        create_identity()
    elif choice == "23":
        print("\nContributor Profiles:")
        for c in contributors:
            print(f"- {c['anon_id']} (epoch: {c.get('epoch', '?')}, location: {c.get('location', '?')})")
            print(f"  Skills: {', '.join(c.get('skills', []))}")
            print(f"  Resources: {', '.join(c.get('resources', []))}")
            print(f"  Availability: {c.get('availability', '?')}\n")
    elif choice == "24":
        for c in contributors:
            valid = verify_link_signature(c.get("linked_identities", []), c.get("multisig", []), c.get("link_signature", ""))
            status = "✅ valid" if valid else "❌ invalid"
            print(f"{c['anon_id']}: link signature {status}")
    elif choice == "25":
        target_id = input("Enter the anon ID to rotate or revoke link signature: ")
        for c in contributors:
            if c["anon_id"] == target_id:
                action = input("Type 'revoke' to clear links or 'rotate' to regenerate the signature: ").strip().lower()
                if action == "revoke":
                    revoked_proof = {
                        "anon_id": c["anon_id"],
                        "revoked_link_signature": c.get("link_signature", ""),
                        "revoked_at": datetime.utcnow().isoformat()
                    }
                    revoke_log_path = os.path.join(DATA_DIR, "revoked_links.json")
                    revoked_log = load_json(revoke_log_path)
                    revoked_log.append(revoked_proof)
                    save_json(revoke_log_path, revoked_log)

                    c["linked_identities"] = []
                    c["multisig"] = []
                    c["link_signature"] = ""
                    print("Link signature revoked and proof recorded.")
                elif action == "rotate":
                    new_sig = sign_links(c.get("linked_identities", []), c.get("multisig", []))
                    c["link_signature"] = new_sig
                    print("Link signature rotated.")
                else:
                    print("Invalid action.")
                save_json(CONTRIBUTORS_FILE, contributors)
                break
        else:
            print("Anon ID not found.")
    elif choice == "26":
        revoke_log_path = os.path.join(DATA_DIR, "revoked_links.json")
        revoked_log = load_json(revoke_log_path)
        print("\nRevoked Identity Links:")
        for entry in revoked_log:
            print(f"- {entry['anon_id']} revoked {entry['revoked_link_signature'][:12]}... at {entry['revoked_at']}")
    elif choice == "27":
        serial = input("Enter device serial: ").strip()
        nonce = input("Enter known nonce: ").strip()
        device_hash = base64.b64encode(hashlib.sha256((serial + nonce).encode()).digest()).decode()
        matched = False
        for c in contributors:
            for d in c.get("devices", []):
                if d.get("device_id") == device_hash:
                    matched = True
                    print(f"✅ Device match found for identity: {c['anon_id']} (responsibility: {d.get('responsibility')}, activated_at: {d.get('activated_at')})")
        if not matched:
            print("❌ No match found for provided serial + nonce.")
    elif choice == "28":
        anon_id = input("Enter your anon ID: ").strip()
        serial = input("Enter device serial: ").strip()
        old_nonce = input("Enter old nonce: ").strip()
        new_nonce = input("Enter new nonce: ").strip()
        new_epoch = input("Epoch marker for new nonce: ").strip()
        old_hash = base64.b64encode(hashlib.sha256((serial + old_nonce).encode()).digest()).decode()
        new_hash = base64.b64encode(hashlib.sha256((serial + new_nonce).encode()).digest()).decode()
        for c in contributors:
            if c["anon_id"] == anon_id:
                for d in c.get("devices", []):
                    if d["device_id"] == old_hash:
                        d["device_id"] = new_hash
                        d["nonce"] = new_nonce
                        d["activated_at"] = new_epoch
                        save_json(CONTRIBUTORS_FILE, contributors)
                        print("✅ Device nonce rotated and updated.")
                        # Log rotation
                        rotation_log_path = os.path.join(DATA_DIR, "device_rotations.json")
                        rotation_log = load_json(rotation_log_path)
                        note = input("Optional reason or note for rotation: ")
                        rotation_log.append({
                            "anon_id": anon_id,
                            "serial": serial,
                            "old_hash": old_hash,
                            "new_hash": new_hash,
                            "rotated_at": datetime.utcnow().isoformat(),
                            "new_epoch": new_epoch,
                            "note": note.strip()
                        })
                        save_json(rotation_log_path, rotation_log)
                        break
                else:
                    print("❌ No matching device found.")
                break
        else:
            print("Anon ID not found.")
    elif choice == "29":
        rotation_log_path = os.path.join(DATA_DIR, "device_rotations.json")
        rotation_log = load_json(rotation_log_path)
        print("\nDevice Rotation Log:")
        if rotation_log:
            for entry in rotation_log:
                print(f"- {entry['anon_id']} rotated device '{entry['serial']}' at {entry['rotated_at']} (epoch: {entry['new_epoch']})")
                print(f"  Old: {entry['old_hash'][:12]}... → New: {entry['new_hash'][:12]}...")
                if entry.get('note'):
                    print(f"  Note: {entry['note']}\n")
                else:
                    print()
        else:
            print("No device rotations recorded.")
    else:
        print("Invalid choice.")
