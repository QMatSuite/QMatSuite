/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.consts;


public class Constants {
	public enum ProgramName{
		PW,
		PH,
		CP,
		BANDS,
		DOS,
		DYNMAT
	}
	public enum EnumNameList {
		//pw.x
		CONTROL,
		SYSTEM,
		ELECTRONS,
		IONS,
		CELL
	}
	public enum EnumCard {
		//pw.x
		ATOMIC_SPECIES,
		ATOMIC_POSITIONS,
		K_POINTS,
		CELL_PARAMETERS,
		CONSTRAINTS,
		OCCUPATIONS,
		ATOMIC_FORCES
	}
	public enum EnumCalc{
		//NULL,//no calculation
		//GEO,//not a calculation, just here for programming convenience
		SCF,
		OPT,
		DOS,
		BANDS,
		BOMD,
		TDDFT
	}
	public enum EnumStep{
		//NULL,//no calculation
		GEO,
		SCF,
		NSCF,
		OPT,
		DOS,
		BANDS,
		BOMD,
		TDDFT
	}
	public interface enumInProgram {
    }
	public enum EnumUnitCellLength implements enumInProgram{
		bohr,angstrom,pm
	}
	public enum EnumUnitCellParameter implements enumInProgram{
		alat,bohr,angstrom,pm
	}
	public enum EnumUnitCellAngle implements enumInProgram{
		degree,radian
	}
	public enum EnumUnitAtomPos implements enumInProgram{
		alat,bohr,angstrom,crystal
	}
	public enum EnumUnitEnergy implements enumInProgram{
		Ry,eV
	}
	public enum EnumFunctional implements enumInProgram{
		LDA,GGA,PBE,PBESOL
	}
	public enum EnumMixingMode implements enumInProgram{
		plain("plain"),
		tf("TF"),
		ltf("local-TF");
		
		private String name;
		
		private EnumMixingMode(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumOccupations implements enumInProgram{
		smearing,tetrahedra,tetrahedra_lin,tetrahedra_opt,fixed
	}
	public enum EnumPP implements enumInProgram{
		PAW("PAW"),
		USPP("Ultrasoft"),
		NCPP("Norm-conserving");
		
		private String name;
		
		private EnumPP(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumNumCondition implements enumInProgram{
		no,positive,nonNegative
	}
	public enum EnumSmearing implements enumInProgram{
		gauss("gaussian"),
		mp("methfessel-paxton"),
		mv("marzari-vanderbilt"),
		fd("fermi-dirac");
		
		private String name;
		
		private EnumSmearing(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
}
