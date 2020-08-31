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

import core.com.consts.ConstantsGeneral;

public class Constants extends ConstantsGeneral{
	//cannot change name! Otherwise incompatible with previous saved calculation files
	private Constants() {
	}
	
	public enum ProgramName{
		PW,
		PH,
		CP,
		BANDS,
		DOS,
		DYNMAT,
		TURBO_LANCZOS,
		TURBO_SPECTRUM
	}
	public enum EnumNameList {
		//pw.x
		CONTROL,
		SYSTEM,
		ELECTRONS,
		IONS,
		CELL,
		//dos.x
		DOS,
		//projwfc.x
		PROJWFC,
		//turbo_lanczos.x
		lr_input,
		lr_control,
		lr_post,
		//bands.x
		BANDS,
		//ph.x
		INPUTPH,
		//q2r.x and matdyn.x
		input,
		//neb.x
		PATH
	}
	public enum EnumFileCategory{
		save("QuantumVITAS save"),directory("Directory"),stdin("Input (std)"),
		stdout("Output (std)"),xmlout("Output (xml)"),crash("Crash"),stderr("Error (std)"),
		unknown("Unknown"),dos("Density of states"),bandsDatGnu("Bands Data (gnu)"),phononBandsGnu("Phonon Bands (gnu)"),
		tddftPlotSDat("TDDFT Data (plot_S)"),
		pdosall("All PDOS files"),pbands("Projected bands");
		
		private String name;
		
		private EnumFileCategory(String name) {
			this.name = name;
		}
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumAnalysis{
		info("Information"),
		text("Raw text"),
		plot2D("Plots"),
		plot3D("3D Geometry");
		
		private String name;
		
		private EnumAnalysis(String name) {
			this.name = name;
		}
		
		@Override
		public String toString() {
			return name;
		}

		public String getName() {
			return name;
		}

		public void setName(String name) {
			this.name = name;
		}
	}
	public enum EnumCard {
		//pw.x
		ATOMIC_SPECIES,
		ATOMIC_POSITIONS,
		K_POINTS,
		CELL_PARAMETERS,
		CONSTRAINTS,
		OCCUPATIONS,
		ATOMIC_FORCES,
		//any program, end part
		END;
	}
	public enum EnumCalc implements core.com.consts.ConstantsGeneral.EnumCalcInterface{
		//NULL,//no calculation
		//GEO,//not a calculation, just here for programming convenience
		SCF("Self consistency (scf)", "SCF"),
		OPT("Structure optimization", "OPT"),
		DOS("Electronic density of states (DOS)", "DOS"),
		BANDS("Electronic band structure", "Bands"),
		BOMD("Molecular Dynamics (Born–Oppenheimer type, BOMD)", "MD"),
		TDDFT("TDDFT", "TDDFT"),
		PHONON("Phonon","PH"),
		NEB("Nudget Elastic Band","NEB");

		private String longName,
		shortName;
		
		private EnumCalc(String longName, String shortName) {
	        this.longName = longName;
	        this.shortName = shortName;
	    }
		public String getLong() {
			return longName;
		}
		public String getShort() {
			return shortName;
		}
		public static EnumCalc shortReverse(String shortTmp) {
			if(shortTmp==null) return null;
			switch(shortTmp) {
				case "SCF":return SCF;
				case "OPT":return OPT;
				case "DOS":return DOS;
				case "Bands":return BANDS;
				case "MD":return BOMD;
				case "TDDFT":return TDDFT;
				case "PH":return PHONON;
				case "NEB":return NEB;
				default:return null;
			}
		}
	}
	public enum EnumStep implements core.com.consts.ConstantsGeneral.EnumStepInterface{
		//NULL,//no calculation
		GEO("GEO"),
		SCF("SCF"),
		NSCF("NSCF"),
		OPT("OPT"),
		DOS("DOS"),
		PDOS("PDOS"),
		BANDS("Bands"),
		BANDSPP("Bands PP"),
		BANDSPP2("Bands PP 2"),
		BOMD("MD"),
		TDDFT("Turbo_lanczos"),
		TDDFT2("Turbo_spectrum"),
		PH("ph.x"),//no relation to the actual command name. Can be anything, just for display in the GUI
		Q2R("q2r.x"),
		MATDYN("matdyn.x"),
		NEB("NEB");
		private String name;
		
		private EnumStep(String name) {
	        this.name = name;
	    }
		public String getName() {
			return name;
		}
	}
	
	public enum EnumUnitCellLength implements EnumInProgram{
		bohr,angstrom,pm
	}
	public enum EnumUnitCellParameter implements EnumInProgram{
		alat,bohr,angstrom,pm
	}
	public enum EnumUnitCellAngle implements EnumInProgram{
		degree,radian
	}
	public enum EnumUnitAtomPos implements EnumInProgram{
		//must be exactly the same as used in the input file
		//Card: ATOMIC_POSITIONS { alat | bohr | angstrom | crystal | crystal_sg }
		alat,bohr,angstrom,crystal
	}
	public enum EnumUnitEnergy implements EnumInProgram{
		Ry,eV
	}
	public enum EnumUnitTime implements EnumInProgram{
		Ry("Rydberg a.u."),
		fs("fs");
		
		private String name;
		
		private EnumUnitTime(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumFunctional implements EnumInProgram{
		LDA,GGA,PBE,PBESOL
	}
	public enum EnumMixingMode implements EnumInProgram{
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
	public enum EnumOccupations implements EnumInProgram{
		smearing,tetrahedra,tetrahedra_lin,tetrahedra_opt,fixed
	}
	public enum EnumSummation implements EnumInProgram{
		smearing,tetrahedra,tetrahedra_lin,tetrahedra_opt,from_input
	}
	public enum EnumPP implements EnumInProgram{
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
	public enum EnumNumCondition implements EnumInProgram{
		no,positive,nonNegative,gt3//gt3 is >=3, for NEB
	}
	public enum EnumSmearing implements EnumInProgram{
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
	public enum EnumIonOptMethod implements EnumInProgram{
		bfgs,damp;
	}
	public enum EnumIonMdMethod implements EnumInProgram{
		verlet("verlet"),
		langevin("langevin"),
		langevinsmc("langevin-smc");
		
		private String name;
		
		private EnumIonMdMethod(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumIonVcmdMethod implements EnumInProgram{
		beeman;
	}
	public enum EnumThermalstat implements EnumInProgram{
		rescaling("rescaling"),
		rescalev("rescale-v"),
		rescaleT("rescale-T"),
		reduceT("reduce-T"),
		berendsen("berendsen"),
		andersen("andersen"),
		svr("svr"),
		initial("initial"),
		non("not_controlled");
		
		private String name;
		
		private EnumThermalstat(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumStringMethod implements EnumInProgram{
		neb("neb","nudget-elastic-band (NEB)"),
		smd("sm","string-method-dynamics (SMD)");
		
		private String displayName,
		name;
		
		private EnumStringMethod(String name, String displayName) {
			this.displayName = displayName;
	        this.name = name;
	    }
		@Override
		public String toString() {
			return displayName;
		}
		public String getName() {
			return name;
		}
	}
	public enum EnumOptSchemeNeb implements EnumInProgram{
		sd("sd","(sd) steepest descent"),
		bd("broyden","(broyden) quasi-Newton Broyden"),
		bd2("broyden2","(broyden2) quasi-Newton Broyden variant"),
		qm("quick-min","(quick-min) projected velocity Verlet"),
		lg("langevin","(langevin) finite temperature langevin");
		
		private String displayName,
		name;
		
		private EnumOptSchemeNeb(String name, String displayName) {
			this.displayName = displayName;
	        this.name = name;
	    }
		@Override
		public String toString() {
			return displayName;
		}
		public String getName() {
			return name;
		}
		
	}
	public enum EnumCellOptMethod implements EnumInProgram{
		no("none"),
		sd("sd"),
		damppr("damp-pr"),
		dampw("damp-w"),
		bfgs("bfgs");
		
		private String name;
		
		private EnumCellOptMethod(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumCellMdMethod implements EnumInProgram{
		none,pr,w;
	}
	public enum EnumKUnit implements EnumInProgram{
		tpiba,automatic,crystal,gamma,tpiba_b,crystal_b,tpiba_c,crystal_c
	}
	public enum EnumHybridFunc implements EnumInProgram{
		defaultFunctional,
		pbe0,hse,b3lyp,gaupbe
	}
	public enum EnumVdw implements EnumInProgram{
		no("none","none"),
		dftd2("dft-d","Grimme's DFT-D2"),
		dftd3("dft-d3","Grimme's DFT-D3"),
		ts("ts-vdw","Tkatchenko-Scheffler dispersion corrections"),
		xdm("xdm","XDM (Exchange-hole dipole-moment model)");
		
		private String displayName,
		name;
		
		private EnumVdw(String name, String displayName) {
			this.displayName = displayName;
	        this.name = name;
	    }
		@Override
		public String toString() {
			return displayName;
		}
		public String getName() {
			return name;
		}
		
	}
	public enum EnumHybridTreat implements EnumInProgram{
		gb("gygi-baldereschi"),
		vs("vcut_spherical"),
		vw("vcut_ws"),
		no("none");
		
		private String name;
		
		private EnumHybridTreat(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumKUnitBands implements EnumInProgram{
		tpiba_b("2pi/a","tpiba_b"),crystal_b("crystal","crystal_b");
		private String displayName,
		name;
		
		private EnumKUnitBands(String displayName, String name) {
			this.displayName = displayName;
	        this.name = name;
	    }
		@Override
		public String toString() {
			return displayName;
		}
		public String getName() {
			return name;
		}
	}
	public enum EnumPolarizability implements EnumInProgram{
		alpha_xx(1),//default
		alpha_yy(2),alpha_zz(3),full(4);
		private int index;
		
		private EnumPolarizability(int index) {
	        this.index = index;
	    }
		public int getIndex() {
			return this.index;
		}
	}
	public enum EnumExtrapolation implements EnumInProgram{
		osc,constant,no
	}
	public enum EnumAsr implements EnumInProgram{
		no("no"),
		simple("simple"),
		crystal("crystal"),
		oneDimensional("one-dim"),
		zeroDimensional("zero-dim");
		
		private String name;
		
		private EnumAsr(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
	public enum EnumTddftUnitEnergy implements EnumInProgram{
		Ry(0,"Rydbergs"),//default
		eV(1,"Electron volts"),nmpeV(2,"Nanometres per electron volts");
		private int index;
		private String fullName;
		
		private EnumTddftUnitEnergy(int index, String fullName) {
	        this.index = index;
	        this.fullName = fullName;
	    }
		@Override
		public String toString() {
			return fullName;
		}
		public int getIndex() {
			return this.index;
		}
	}
	public enum EnumCellDoFree implements EnumInProgram{
		all("all"),
		ibrav("ibrav"),
		xonly("x"),
		yonly("y"),
		zonly("z"),
		xy("xy"),
		xz("xz"),
		yz("yz"),
		xyz("xyz"),
		shape("shape"),
		volume("volume"),
		xy2d("2Dxy"),
		shape2d("2Dshape"),
		epitaxialab("epitaxial_ab"),
		epitaxialac("epitaxial_ac"),
		epitaxialbc("epitaxial_bc");
		
		private String name;
		
		private EnumCellDoFree(String name) {
	        this.name = name;
	    }
		@Override
		public String toString() {
			return name;
		}
	}
}
