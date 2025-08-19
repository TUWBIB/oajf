### OAJF

A simple tool to display a list of journals covered by an institution's policy on funding for open access publishing.

**Live site:** [https://oajf.tuwien.ac.at](https://oajf.tuwien.ac.at)

### Mentions

OAJF is based on:
- Flask
- MariaDB
- TailwindCSS
- Iconify

OAJF makes use of the following icon sets:
- [Heroicons](https://heroicons.com/)
- [VSCode Icons](https://github.com/vscode-icons/vscode-icons)
- [Element Plus Icons](https://github.com/element-plus/element-plus-icons)

### Installation and Development Environment

#### Prerequisites

At the time of writing, OAJF uses the latest official versions of the frameworks mentioned. No effort has been made to determine minimum version requirements.

#### Steps

1. **Clone the Repository**:
   - Clone the repository to your local machine.

2. **Virtual Python Environment**:
   - Create a Python virtual environment and install the needed libraries:
     ```bash
     pip3 install -r virtenv
     ```

3. **Install Node Modules**:
   - Rely on `package.json` and install everything in one go:
     ```bash
     npm i
     ```
   - Or step by step:
     ```bash
     npm i -D tailwindcss @tailwindcss/cli
     npm i -D @iconify/tailwind4
     npm i -D @iconify-json/heroicons
     npm i -D @iconify-json/vscode-icons
     npm i -D @iconify-json/ep
     ```

4. **Database**:
   - Create a MariaDB database as described in the file `sql/drop_create_database.sql`.
   - Apply the `sql/create_schema.sql` file to create the needed tables.
   - Copy `oajf/config.py.sample` to `oajf/config.py` and configure the database credentials.

5. **First Run and Further Steps**:
   - In principle, you should now be able to run:
     ```bash
     ./babel_collect.sh
     ```
     to create the file for the English translation.

   - Run:
     ```bash
     ./tailwind_watch.sh
     ```
     to create the main CSS file.

   - Start a local server with:
     ```bash
     ./runserver_loc.sh
     ```

   - You should now be able to open:
     ```
     http://127.0.0.1:5001
     ```
     and get a page with no content.