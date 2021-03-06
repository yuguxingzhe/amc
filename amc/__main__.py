# Copyright (C) 2020  Julien Ripoche, Alexander Tichai, Roland Wirth
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Main routine of the Angular Momentum Coupling."""

from __future__ import (division, absolute_import, print_function)

import argparse
import os.path
import datetime
import sys

import amc.output
import amc.parser
import amc.reduction
import amc.error


class _VersionAction(argparse.Action):

    def __init__(self,
                 option_strings,
                 version=None,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help="show program's version number and exit"):
        super(_VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)
        self.version = version

    def __call__(self, parser, namespace, values, option_string=None):
        import textwrap

        version = self.version
        if version is None:
            version = parser.version
        print(textwrap.dedent(version))
        parser.exit()


def parse_command_line():
    """Return run commands from the Command Line Interface.

    Returns:
        (Namespace): Appropriate commands to manage the program's run.

    """

    version_string = """\
    amc {version}
    Copyright (C) 2020 {author}
    License GPLv3+: GNU GPL version 3 or later <https://gnu.org/licenses/gpl.html>.
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.
    """.format(version=amc.__version__, author=amc.__author__)

    parser = argparse.ArgumentParser(
        description=
        "Perform angular-momentum coupling on the given equations"
        "and return the result as a LaTeX file.")

    parser.add_argument('source', help='input file')
    parser.add_argument('-o', '--output', nargs=1, help='output file')
    parser.add_argument('--collect-ninejs', action='store_true', help='Build 9j-coefficients from products of 6j-coefficients.')
    parser.add_argument('--keep-threejs', action='store_true', help='Keep 3j-coefficients in the output.')
    parser.add_argument('--wet-convention', choices=['wigner', 'sakurai'], default='wigner',
                        help='Convention used for Wigner-Eckart reduced matrix elements.')
    parser.add_argument('-V', '--version', action=_VersionAction, version=version_string)
    parser.add_argument('-v', '--verbose', action='count', help='Increase verbosity', default=0)
    parser.add_argument('-k', '--keep-going', action='store_true', help='Do not stop in case of errors.')

    args = parser.parse_args()

    return args


def main():
    """Launch the AMC program."""

    # Parse command line
    run_arguments = parse_command_line()

    # Text
    parser = amc.parser.Parser(optimize=True)
    with open(run_arguments.source) as f:
        parser.parse(f.read(), debug=0)
    if run_arguments.verbose > 0:
        print('# Known Tensors #')
        for tensor in parser.tensors.values():
            print(tensor)
        print()
        print('# Equations #')
        for eqn in parser.equations:
            print('Original')
            print(eqn)
            print()
            eqn_permuted = eqn.expand_permutations()
            print('Permuted')
            print(eqn_permuted)
            print()
            eqn_expanded = eqn_permuted.expand()
            print('Expanded')
            print(eqn_expanded)
            print()
    equations = parser.equations

    # Output file
    if run_arguments.output is None:
        dirname, basename = os.path.split(run_arguments.source)
        if '.' in basename:
            basename = basename.rsplit('.', 1)[0] + '.tex'
        else:
            basename = basename + '.tex'
        output_file = os.path.join(dirname, basename)
    else:
        output_file = run_arguments.output[0]

    # Start computing
    print("Running...")
    start_time = datetime.datetime.now()

    results = []
    error_eqns = []

    # Angular-momentum reduction
    for i, equation in enumerate(equations):
        print("Equation {0:3d}/{1:3d}...".format(i + 1, len(equations)), flush=True)
        try:
            res = amc.reduction.reduce_equation(
                equation,
                collect_ninejs=run_arguments.collect_ninejs,
                convention=run_arguments.wet_convention,
                verbose=run_arguments.verbose > 1)
            results.append((i, res))
        except amc.error.Error as e:
            error_eqns.append(i+1)

            if isinstance(e.__cause__, amc.error.GraphNotReducibleError):
                print('### Could not fully reduce Yutsis graph for term {}. ###'.format(e.term_number + 1))
            elif isinstance(e.__cause__, amc.error.GraphNotOrientableError):
                print((
                    '### Resulting Yutsis graph for term {} could not be oriented. ###\n'
                    'This is often caused by contracting like indices (creator with creator or annihilator with annihilator).\n'
                    'The following pairs of 3jm symbols may provide more information:'
                    ).format(e.term_number + 1))
                for a, b in e.__cause__.offending_pairs:
                    print('- {!s} <> {!s}'.format(a, b))

            print('Expression that caused the error was: {!s} <- {!s}\n'.format(e.lhs, e.term))

            if not run_arguments.keep_going:
                sys.exit(1)

    output = amc.output.latex.equations_to_document(results, print_threejs=run_arguments.keep_threejs)

    with open(output_file, 'wt') as f:
        f.write(output)

    print("Time elapsed: %s.\n" % (datetime.datetime.now() - start_time))

    if error_eqns:
        print("AMC FAILED!")
        print("Failed equations: {}".format(', '.join(map(str, error_eqns))))
    else:
        print("AMC ended successfully!")


if __name__ == "__main__":
    main()

