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
package input;

import java.io.File;
import java.util.ArrayList;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import agent.InputAgentBands;
import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentNscf;
import agent.InputAgentOpt;
import agent.InputAgentScf;
import agent.WrapperBoolean;
import agent.WrapperInteger;
import agent.WrapperString;
import app.input.Kpoint;
import app.input.geo.Atom;
import app.input.geo.Element;
import com.consts.PhysicalConstants;
import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumKUnitBands;
import com.consts.Constants.EnumMixingMode;
import com.consts.Constants.EnumNameList;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumThermalstat;
import com.consts.Constants.EnumUnitEnergy;
import com.consts.Constants.EnumUnitTime;
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;

public class PwInput extends QeInput{
	
	private ArrayList<Element> elementList = new ArrayList<Element>();
	private ArrayList<Atom> atomList = new ArrayList<Atom>();
	private boolean flagLoadGeo=false;
	private boolean flagLoadScf=false;
	
	public PwInput() {
		super("pw");
		//namelists
		sectionDict.put("CONTROL", new NameList(EnumNameList.CONTROL));
		sectionDict.put("SYSTEM", new NameList(EnumNameList.SYSTEM));
		sectionDict.put("ELECTRONS", new NameList(EnumNameList.ELECTRONS));
		sectionDict.put("IONS", new NameList(EnumNameList.IONS));
		sectionDict.put("CELL", new NameList(EnumNameList.CELL));
		//cards
		sectionDict.put("ATOMIC_SPECIES", new Card(EnumCard.ATOMIC_SPECIES));
		sectionDict.put("ATOMIC_POSITIONS", new Card(EnumCard.ATOMIC_POSITIONS));
		sectionDict.put("K_POINTS", new Card(EnumCard.K_POINTS));
		sectionDict.put("CELL_PARAMETERS", new Card(EnumCard.CELL_PARAMETERS));
		sectionDict.put("CONSTRAINTS", new Card(EnumCard.CONSTRAINTS));
		sectionDict.put("OCCUPATIONS", new Card(EnumCard.OCCUPATIONS));
		sectionDict.put("ATOMIC_FORCES", new Card(EnumCard.ATOMIC_FORCES));
		//add relevant parameters
		sectionDict.get("CONTROL").setBoolRequired(true);
		sectionDict.get("CONTROL").addParameter("calculation", new InputValueString("calculation","scf",true));//always write to make clear
		sectionDict.get("CONTROL").addParameter("restart_mode", new InputValueString("restart_mode","from_scratch",false));
		sectionDict.get("CONTROL").addParameter("max_seconds", new InputValueDouble("max_seconds",1.0E7,false));
		sectionDict.get("CONTROL").addParameter("tprnfor", new InputValueBoolean("tprnfor",false,false));
		sectionDict.get("CONTROL").addParameter("tstress", new InputValueBoolean("tstress",false,false));
		sectionDict.get("CONTROL").addParameter("pseudo_dir", new InputValueString("pseudo_dir",false));
		sectionDict.get("CONTROL").addParameter("nstep", new InputValueInt("nstep",1,false));
		sectionDict.get("CONTROL").addParameter("dt", new InputValueDouble("dt",20.0,false));
		sectionDict.get("CONTROL").addParameter("etot_conv_thr", new InputValueDouble("etot_conv_thr",1.0E-4,false));
		sectionDict.get("CONTROL").addParameter("forc_conv_thr", new InputValueDouble("forc_conv_thr",1.0E-3,false));
		
		sectionDict.get("SYSTEM").setBoolRequired(true);
		sectionDict.get("SYSTEM").addParameter("ibrav", new InputValueInt("ibrav"));
		sectionDict.get("SYSTEM").addParameter("A", new InputValueDouble("A"));
		sectionDict.get("SYSTEM").addParameter("B", new InputValueDouble("B",false));
		sectionDict.get("SYSTEM").addParameter("C", new InputValueDouble("C",false));
		sectionDict.get("SYSTEM").addParameter("cosBC", new InputValueDouble("cosBC",false));
		sectionDict.get("SYSTEM").addParameter("cosAC", new InputValueDouble("cosAC",false));
		sectionDict.get("SYSTEM").addParameter("cosAB", new InputValueDouble("cosAB",false));
		sectionDict.get("SYSTEM").addParameter("nat", new InputValueInt("nat",true));
		sectionDict.get("SYSTEM").addParameter("ntyp", new InputValueInt("ntyp",true));
		sectionDict.get("SYSTEM").addParameter("ecutwfc", new InputValueDouble("ecutwfc",true));
		sectionDict.get("SYSTEM").addParameter("ecutrho", new InputValueDouble("ecutrho",false));
		sectionDict.get("SYSTEM").addParameter("lda_plus_u", new InputValueBoolean("lda_plus_u",false,false));
		sectionDict.get("SYSTEM").addParameter("Hubbard_U", new InputValueDoubleArray("Hubbard_U",false));
		sectionDict.get("SYSTEM").addParameter("starting_magnetization", new InputValueDoubleArray("starting_magnetization",false));
		sectionDict.get("SYSTEM").addParameter("angle1", new InputValueDoubleArray("angle1",false));
		sectionDict.get("SYSTEM").addParameter("angle2", new InputValueDoubleArray("angle2",false));
		sectionDict.get("SYSTEM").addParameter("nspin", new InputValueInt("nspin",1,false));
		sectionDict.get("SYSTEM").addParameter("noncolin", new InputValueBoolean("noncolin",false,false));
		sectionDict.get("SYSTEM").addParameter("lspinorb", new InputValueBoolean("lspinorb",false,false));
		sectionDict.get("SYSTEM").addParameter("occupations", new InputValueString("occupations",true));
		sectionDict.get("SYSTEM").addParameter("degauss", new InputValueDouble("degauss",0.0,true));
		sectionDict.get("SYSTEM").addParameter("smearing", new InputValueString("smearing",EnumSmearing.gauss.toString(),true));
		sectionDict.get("SYSTEM").addParameter("nbnd", new InputValueInt("nbnd",false));
		
		sectionDict.get("ELECTRONS").addParameter("electron_maxstep", new InputValueInt("electron_maxstep",100,false));
		sectionDict.get("ELECTRONS").addParameter("conv_thr", new InputValueDouble("conv_thr",1e-6,false));
		sectionDict.get("ELECTRONS").addParameter("mixing_mode", new InputValueString("mixing_mode",EnumMixingMode.plain.toString(),false));
		sectionDict.get("ELECTRONS").addParameter("mixing_beta", new InputValueDouble("mixing_beta",0.7,false));
		sectionDict.get("ELECTRONS").addParameter("scf_must_converge", new InputValueBoolean("scf_must_converge",true,false));
		
		sectionDict.get("IONS").addParameter("ion_dynamics", new InputValueString("ion_dynamics","bfgs",false));
		sectionDict.get("IONS").addParameter("ion_temperature", new InputValueString("ion_temperature","not_controlled",false));
		
		sectionDict.get("IONS").addParameter("tempw", new InputValueDouble("tempw",300.0,false));
		sectionDict.get("IONS").addParameter("tolp", new InputValueDouble("tolp",100.0,false));
		sectionDict.get("IONS").addParameter("delta_t", new InputValueDouble("delta_t",1.0,false));
		sectionDict.get("IONS").addParameter("nraise", new InputValueInt("nraise",1,false));
		
		
		sectionDict.get("CELL").addParameter("cell_dynamics", new InputValueString("cell_dynamics","bfgs",false));
		sectionDict.get("CELL").addParameter("press", new InputValueDouble("press",0.0,false));
		sectionDict.get("CELL").addParameter("press_conv_thr", new InputValueDouble("press_conv_thr",0.5,false));
		sectionDict.get("CELL").addParameter("cell_dofree", new InputValueString("cell_dofree","all",false));
		
		//"body" means the part without "...=" prefix. We assume here at most only one such part exists for one namelist
		sectionDict.get("ATOMIC_SPECIES").addParameter("body",new InputValueString("body","",false));
		sectionDict.get("ATOMIC_POSITIONS").addParameter("body",new InputValueString("body","",false));
		sectionDict.get("K_POINTS").addParameter("body",new InputValueString("body","",false));
		sectionDict.get("CELL_PARAMETERS").addParameter("body",new InputValueString("body","",false));
		/* setValue("SYSTEM", "lda_plus_u", true);
		 * setValue("SYSTEM", "ecutwfc", 25); String outStr = setValue("SYSTEM",
		 * "ecutwfc", "10"); System.out.println(outStr); if
		 * (sectionDict.get("SYSTEM").getValue("ecutwfc") instanceof InputValueInt) {
		 * System.out.println("int"); }
		 */
	}
	
	
	@Override
	public void loadAgent(InputAgentGeo ia1) {
		flagLoadScf = false;
		try {
			//setValue("SYSTEM","ibrav",(Integer) null);
			setValue("SYSTEM","ibrav",ia1.ibrav);
			setValue("SYSTEM","A",ia1.convCellLength(ia1.cellA));
			setValue("SYSTEM","B",ia1.convCellLength(ia1.cellB));
			setValue("SYSTEM","C",ia1.convCellLength(ia1.cellC));
			setValue("SYSTEM","cosBC",ia1.convCellAngle(ia1.cellAngleBC));
			setValue("SYSTEM","cosAC",ia1.convCellAngle(ia1.cellAngleAC));
			setValue("SYSTEM","cosAB",ia1.convCellAngle(ia1.cellAngleAB));
			
			//set section options
			if(ia1.ibrav.equals(0)) {
				setSectionRequired("CELL_PARAMETERS",true);
				setRequiredAndWrite("CELL_PARAMETERS","body",true,true);
				String optTmp;
				double scale = 1.0;
				switch(ia1.unitCellParameter) {
					case alat:setRequiredAndWrite("SYSTEM","A",true,true);optTmp="(alat)";break;
					case angstrom:setRequiredAndWrite("SYSTEM","A",false,false);optTmp="(angstrom)";break;
					case bohr:setRequiredAndWrite("SYSTEM","A",false,false);optTmp="(bohr)";break;
					case pm:setRequiredAndWrite("SYSTEM","A",false,false);optTmp="(angstrom)";scale=1.0/100;break;
					default:optTmp=null;break;
				}
				if(optTmp!=null) {
					setSectionOption("CELL_PARAMETERS",optTmp);
					if (!ia1.vectorA1.isNull() && !ia1.vectorA2.isNull() && !ia1.vectorA3.isNull() &&
							!ia1.vectorB1.isNull() && !ia1.vectorB2.isNull() && !ia1.vectorB3.isNull() &&
									!ia1.vectorC1.isNull() && !ia1.vectorC2.isNull() && !ia1.vectorC3.isNull() ) {
						WrapperString wp = new WrapperString(
										" "+ia1.vectorA1.getValue()*scale+" "+ia1.vectorA2.getValue()*scale+" "+ia1.vectorA3.getValue()*scale+"\n"+
										" "+ia1.vectorB1.getValue()*scale+" "+ia1.vectorB2.getValue()*scale+" "+ia1.vectorB3.getValue()*scale+"\n"+
										" "+ia1.vectorC1.getValue()*scale+" "+ia1.vectorC2.getValue()*scale+" "+ia1.vectorC3.getValue()*scale);
						setValue("CELL_PARAMETERS","body",wp);
					}
				}
			}
			else {
				setRequiredAndWrite("SYSTEM","A",true,true);
				setSectionRequired("CELL_PARAMETERS",false);
				setRequiredAndWrite("CELL_PARAMETERS","body",false,false);
			}
			
			setValue("SYSTEM","nat",new WrapperInteger(ia1.atomList.size()));
			setValue("SYSTEM","ntyp",new WrapperInteger(ia1.elemListAll.size()));
			
			setRequiredAndWrite("CONTROL","pseudo_dir",true,true);
			if(ia1.getPseudodir()!=null) {
				//*****to solve the issue of QE 6.4.1 windows version
				//*****careful when cross platform
				setValue("CONTROL","pseudo_dir",new WrapperString(ia1.getPseudodir().replace("\\", "/")));
			}
					
			setRequiredAndWrite("ATOMIC_SPECIES","body",true,true);
			elementList.clear();
			String atomSpecTmp = "";
			for (int i=0;i<ia1.elemListAll.size();i++) {
				Element elTmp = ia1.elemListAll.get(i);
				elementList.add(elTmp);
				
				
				if(elTmp.getPseudoPotFile()==null || elTmp.getPseudoPotFile().isEmpty()) {
					//write pseudopotential file anyway
					atomSpecTmp+=(elTmp.getAtomSpecies()+"  "+elTmp.getAtomMass().toString()+"\n");
					errorMessage+=("Missing pseudo potential file for "+(i+1)+"th atom: "+elTmp.getAtomSpecies()+"\n");
				}
				else {
					File fl = new File(elTmp.getPseudoPotFile());
					atomSpecTmp+=(elTmp.getAtomSpecies()+"  "+elTmp.getAtomMass().toString()+"  "+fl.getName()+"\n");
					if(!elTmp.isPseudoValid()){errorMessage+=("Pseudo potential file invalid for "+(i+1)+"th atom: "+elTmp.getAtomSpecies()+"\n");}
				}
			}
			setValue("ATOMIC_SPECIES","body",new WrapperString(atomSpecTmp));
			
			setRequiredAndWrite("ATOMIC_POSITIONS","body",true,true);
			setSectionOption("ATOMIC_POSITIONS","("+ia1.unitAtomPos+")");//ia1.unitAtomPos will not be null
			atomList.clear();
			String atomPosTmp = "";
			for (int i=0;i<ia1.atomList.size();i++) {
				Atom atTmp = ia1.atomList.get(i);
				atomList.add(atTmp);
				atomPosTmp+=(atTmp.getAtomSpecies().toString()
						+"  "+atTmp.getXcoor().getX().toString()
						+"  "+atTmp.getYcoor().getX().toString()
						+"  "+atTmp.getZcoor().getX().toString()
						+"  "+(atTmp.getXcoor().getBoolFix()?"0":"1")
						+"  "+(atTmp.getYcoor().getBoolFix()?"0":"1")
						+"  "+(atTmp.getZcoor().getBoolFix()?"0":"1")
						+"\n");
			}
			setValue("ATOMIC_POSITIONS","body",new WrapperString(atomPosTmp));
				
			flagLoadGeo = true;
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
		
	}
	@Override
	public void loadAgent(InputAgentScf ia1) {
		flagLoadScf = false;
		try {
			if (!flagLoadGeo) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Info");
		    	alert1.setContentText("You should load Geometry first!");
		    	alert1.showAndWait();
		    	return;
			}
			//set section required
			setSectionRequired("CONTROL",true);setSectionRequired("SYSTEM",true);setSectionRequired("ELECTRONS",true);
			setSectionRequired("ATOMIC_SPECIES",true);setSectionRequired("ATOMIC_POSITIONS",true);setSectionRequired("K_POINTS",true);
			
			//set parameters
			boolean boolMag = ia1.setMag;
			setValue("SYSTEM","nspin",ia1.nspin);andExplicitWrite("SYSTEM","nspin",boolMag);
			
			setValue("SYSTEM","noncolin",ia1.noncolin);andExplicitWrite("SYSTEM","noncolin",boolMag);
			setValue("SYSTEM","lspinorb",ia1.boolSoc);andExplicitWrite("SYSTEM","lspinorb",boolMag);
			
			InputValueDoubleArray tmp2 = ((InputValueDoubleArray) sectionDict.get("SYSTEM").getValue("starting_magnetization"));
			tmp2.clearAll();tmp2.setExplicitWrite(false);
			
			if(boolMag && (ia1.nspin.isNull() || !ia1.nspin.getValue().equals(1))) {
				tmp2.setExplicitWrite(true);
				if(ia1.setForElements.getValue()) {
					for(int iele=0;iele<elementList.size();iele++) {
						tmp2.addElement(elementList.get(iele).getMag(),iele+1);
					}
				}
				else if(ia1.setForAtoms.getValue()) {
					for(int iele=0;iele<atomList.size();iele++) {
						tmp2.addElement(atomList.get(iele).getMag(),iele+1);
					}
				}
			}
			
			InputValueDoubleArray tmpAngle1 = ((InputValueDoubleArray) sectionDict.get("SYSTEM").getValue("angle1"));
			InputValueDoubleArray tmpAngle2 = ((InputValueDoubleArray) sectionDict.get("SYSTEM").getValue("angle2"));
			tmpAngle1.clearAll();tmpAngle1.setExplicitWrite(false);
			tmpAngle2.clearAll();tmpAngle2.setExplicitWrite(false);
			if(boolMag && ia1.nspin.isNull() && ia1.noncolin.getValue()) {
				//non colinear
				andExplicitWrite("SYSTEM","nspin",false);
				tmpAngle1.setExplicitWrite(true);
				tmpAngle2.setExplicitWrite(true);
				if(ia1.setForElements.getValue()) {
					for(int iele=0;iele<elementList.size();iele++) {
						tmpAngle1.addElement(elementList.get(iele).getAngle1(),iele+1);
						tmpAngle2.addElement(elementList.get(iele).getAngle2(),iele+1);
					}
				}
				else if(ia1.setForAtoms.getValue()) {
					for(int iele=0;iele<atomList.size();iele++) {
						tmpAngle1.addElement(atomList.get(iele).getAngle1(),iele+1);
						tmpAngle2.addElement(atomList.get(iele).getAngle2(),iele+1);
					}
				}
			}
			
			setValue("SYSTEM","occupations",ia1.enumOccupation);
			setValue("SYSTEM","degauss",ia1.degauss);
			setValue("SYSTEM","smearing",ia1.enumSmearing);
			
			boolean boolHubbard = ia1.setU;
			
			if(EnumOccupations.smearing.equals(ia1.enumOccupation.getValue())) {
				setRequiredAndWrite("SYSTEM","degauss",true,true);setRequiredAndWrite("SYSTEM","smearing",true,true);
				if(boolHubbard && (ia1.degauss.getValue()==null || ia1.degauss.getValue().equals(0.0))) {
					errorMessage+="For DFT+U calculation, if you use smearing, smearing width must be positive.\n";
				}
			}
			else {
				setRequiredAndWrite("SYSTEM","degauss",false,false);setRequiredAndWrite("SYSTEM","smearing",false,false);
			}
			
			
			setValue("SYSTEM","lda_plus_u",ia1.lda_plus_u);andExplicitWrite("SYSTEM","lda_plus_u",boolHubbard);
			
			
			InputValueDoubleArray tmp = ((InputValueDoubleArray) sectionDict.get("SYSTEM").getValue("Hubbard_U"));
			tmp.setExplicitWrite(boolHubbard);
			tmp.clearAll();
			for(int iele=0;iele<ia1.elementList.size();iele++) {
				Integer tmpIndex = findElementIndex(ia1.elementList.get(iele));
				if(tmpIndex==null) {
					Alert alert1 = new Alert(AlertType.INFORMATION);
			    	alert1.setTitle("Warning");
			    	alert1.setContentText("Cannot find the +U element in the main element list!");
			    	alert1.showAndWait();
				}
				else {
					tmp.addElement(ia1.elementList.get(iele).getHubbardU(),tmpIndex+1);
				}
			}
			
			
			setValue("SYSTEM","ecutwfc",ia1.ecutWfc);
			setValue("SYSTEM","ecutrho",ia1.ecutRho);
			setValue("CONTROL","restart_mode",new WrapperString(ia1.boolRestart.getValue()?"restart":"from_scratch",ia1.boolRestart.isEnabled()));
			setValue("CONTROL","tprnfor",ia1.boolForce);
			setValue("CONTROL","tstress",ia1.boolStress);
			
			setValue("ELECTRONS","electron_maxstep",ia1.nElecMaxStep);
			setValue("ELECTRONS","conv_thr",ia1.elecConv);
			setValue("ELECTRONS","mixing_mode",ia1.enumMixing);
			setValue("ELECTRONS","mixing_beta",ia1.mixBeta);
			
			//kpoints
			if(ia1.boolKGamma.getValue()) {
				setSectionOption("K_POINTS","(gamma)");
			}
			else {
				setSectionOption("K_POINTS","(automatic)");
				setRequiredAndWrite("K_POINTS","body",true,true);
				WrapperString wp = new WrapperString(" "+ia1.nkx.getValue()+" "
				+ia1.nky.getValue()+" "+ia1.nkz.getValue()+" 0 0 0");
				setValue("K_POINTS","body",wp);
			}
			
			
			//correct Units, should be always put at the end
			if(ia1.enumEnergyUnit.equals(EnumUnitEnergy.eV)) {
				((InputValueDouble) sectionDict.get("SYSTEM").getValue("ecutwfc")).multiply(1.0/PhysicalConstants.ryInEV);
				((InputValueDouble) sectionDict.get("SYSTEM").getValue("ecutrho")).multiply(1.0/PhysicalConstants.ryInEV);
				((InputValueDouble) sectionDict.get("SYSTEM").getValue("degauss")).multiply(1.0/PhysicalConstants.ryInEV);
				((InputValueDouble) sectionDict.get("ELECTRONS").getValue("conv_thr")).multiply(1.0/PhysicalConstants.ryInEV);
			}
			
			flagLoadScf = true;
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	
	private Integer findElementIndex(Element el) {
		for(int iele=0;iele<elementList.size();iele++) {
			if (elementList.get(iele).getAtomSpecies().equals(el.getAtomSpecies())) {
				return iele;
			}
		}
		return null;
	}
	@Override
	public void loadAgent(InputAgentOpt ia1) {
		if(ia1==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Info");
	    	alert1.setContentText("Null inputAgentOpt!");
	    	alert1.showAndWait();
	    	return;
		}
		if (!flagLoadGeo || !flagLoadScf) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Info");
	    	alert1.setContentText("You should load Geometry first!");
	    	alert1.showAndWait();
	    	return;
		}
		try {
			//set section required
			setSectionRequired("IONS",true);
			
			setValue("CONTROL","calculation",new WrapperString(ia1.boolRelaxCell.getValue()?"vc-relax":"relax",true));
			setValue("CONTROL","tprnfor",new WrapperBoolean(true,false));
			
			setValue("ELECTRONS","scf_must_converge",ia1.boolScfMustConverge);
			//default for OPT is also 50 steps, although in PwInput the default is 1 step
			setValue("CONTROL","nstep",ia1.nMaxSteps);
			setValue("CONTROL","etot_conv_thr",ia1.numEConv);
			setValue("CONTROL","forc_conv_thr",ia1.numFConv);
			
			setValue("IONS","ion_dynamics",ia1.enumOptMethodIon);
			
			boolean boolCell = ia1.boolRelaxCell.getValue();
			setSectionRequired("CELL",boolCell);
			setValue("CONTROL","tstress",new WrapperBoolean(boolCell,false));
			setValue("CELL","cell_dynamics",ia1.enumOptMethodCell);andExplicitWrite("CELL","cell_dynamics",boolCell);
			setValue("CELL","cell_dofree",ia1.enumCellDoFree);andExplicitWrite("CELL","cell_dofree",boolCell);
			setValue("CELL","press",ia1.numPTarget);andExplicitWrite("CELL","press",boolCell);
			setValue("CELL","press_conv_thr",ia1.numPConv);andExplicitWrite("CELL","press_conv_thr",boolCell);
			
			//correct Units, should be always put at the end
			if(ia1.enumEUnit.equals(EnumUnitEnergy.eV)) {
				((InputValueDouble) sectionDict.get("CONTROL").getValue("etot_conv_thr")).multiply(1.0/PhysicalConstants.ryInEV);
			}
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	@Override
	public void loadAgent(InputAgentMd ia1) {
		try {
			setValue("CONTROL","nstep",ia1.mdSteps);
			setValue("CONTROL","tprnfor",new WrapperBoolean(true,false));
			
			
			setValue("CONTROL","dt",ia1.timeStep);
			if(EnumUnitTime.fs.equals(ia1.enumTimeUnit.getValue())) {
				((InputValueDouble) sectionDict.get("CONTROL").getValue("dt")).multiply(1.0/PhysicalConstants.ryInFs);
			}
			else if(!EnumUnitTime.Ry.equals(ia1.enumTimeUnit.getValue())) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("EnumUnitTime out of bound.");
		    	alert1.showAndWait();
			}
			
			setSectionRequired("IONS",true);
			setValue("IONS","ion_dynamics",ia1.enumMdMethodIon);
			setValue("IONS","ion_temperature",ia1.enumThermalstat);
			boolean blControlT = !ia1.enumThermalstat.equals(EnumThermalstat.non);
			setValue("IONS","tempw",ia1.temperature);andExplicitWrite("IONS","tempw",blControlT);
			setValue("IONS","tolp",ia1.tolp);andExplicitWrite("IONS","tolp",blControlT);
			setValue("IONS","nraise",ia1.nraise);andExplicitWrite("IONS","nraise",blControlT);
			setValue("IONS","delta_t",ia1.deltat);andExplicitWrite("IONS","delta_t",blControlT);
			
			boolean boolCell = ia1.boolMoveCell.getValue();
			setSectionRequired("CELL",boolCell);
			setValue("CONTROL","tstress",new WrapperBoolean(boolCell,false));
			setValue("CONTROL","calculation",new WrapperString(boolCell?"vc-md":"md",true));
			setValue("CELL","cell_dynamics",ia1.enumMdMethodCell);andExplicitWrite("CELL","cell_dynamics",boolCell);
			setValue("CELL","press",ia1.pressure);andExplicitWrite("CELL","press",boolCell);
			setValue("CELL","cell_dofree",ia1.enumCellDoFree);andExplicitWrite("CELL","cell_dofree",boolCell);
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	@Override
	public void loadAgent(InputAgentNscf ia1) {

		try {
			setValue("CONTROL","calculation",new WrapperString("nscf",true));
			setValue("SYSTEM","occupations",ia1.enumOccupation);
			setValue("SYSTEM","degauss",ia1.degauss);
			setValue("SYSTEM","smearing",ia1.enumSmearing);
			WrapperString wp = new WrapperString(" "+ia1.nkx.getValue()+" "
					+ia1.nky.getValue()+" "+ia1.nkz.getValue()+" 0 0 0");
					setValue("K_POINTS","body",wp);
			//correct Units, should be always put at the end
			if(ia1.enumEnergyUnit.equals(EnumUnitEnergy.eV)) {
				((InputValueDouble) sectionDict.get("SYSTEM").getValue("degauss")).multiply(1.0/PhysicalConstants.ryInEV);
			}
			andExplicitWrite("SYSTEM","nbnd",!ia1.nbnd.isNull());
			if(!ia1.nbnd.isNull()) {setValue("SYSTEM","nbnd",ia1.nbnd);}
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	@Override
	public void loadAgent(InputAgentBands ia1) {

		try {
			
			setValue("CONTROL","calculation",new WrapperString("bands",true));
			andExplicitWrite("SYSTEM","nbnd",!ia1.intNBands.isNull());
			if(!ia1.intNBands.isNull()) {setValue("SYSTEM","nbnd",ia1.intNBands);}
			
			setRequiredAndWrite("K_POINTS","body",true,true);
			setSectionOption("K_POINTS","("+((EnumKUnitBands)ia1.enumKUnit.getValue()).getName()+")");

			String kpointTmp = ia1.listKPoints.size()>0 ? Integer.toString(ia1.listKPoints.size())+"\n":"";
			for (int i=0;i<ia1.listKPoints.size();i++) {
				Kpoint kTmp = ia1.listKPoints.get(i);
				kpointTmp += (
							Double.toString(kTmp.getKx())
							+"  "+Double.toString(kTmp.getKy())
							+"  "+Double.toString(kTmp.getKz())
							+"  "+Integer.toString(kTmp.getNk())
							+"  !"+kTmp.getLabel()
							+"\n"
						);
			}
			setValue("K_POINTS","body",new WrapperString(kpointTmp));
			
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	
	
	
}
