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
package agent;

import java.util.ArrayList;

import com.consts.ChemicalElements;
import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import com.consts.Constants.EnumUnitAtomPos;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.consts.Constants.ProgramName;

import app.input.geo.Atom;
import app.input.geo.Element;

public class InputAgentGeo extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7687077166066768185L;
	//cell
	public WrapperInteger ibrav;//ok
	public EnumUnitCellLength unitCellLength;
	public EnumUnitCellAngle unitCellAngle;
	public WrapperDouble cellA;public WrapperDouble cellB;public WrapperDouble cellC;
	public WrapperDouble cellAngleBC;//alpha,celldm(5)
	public WrapperDouble cellAngleAC;//beta,celldm(6)
	public WrapperDouble cellAngleAB;//gamma,celldm(4)
	public EnumUnitCellParameter unitCellParameter;
	public WrapperDouble vectorA1;public WrapperDouble vectorA2;public WrapperDouble vectorA3;
	public WrapperDouble vectorB1;public WrapperDouble vectorB2;public WrapperDouble vectorB3;
	public WrapperDouble vectorC1;public WrapperDouble vectorC2;public WrapperDouble vectorC3;
	//atom
	public EnumUnitAtomPos unitLength;//ok
	public ArrayList<Atom> atomList;//ok
	//elements
	public EnumFunctional typeFunctional;
	public EnumPP typePP;
	public WrapperBoolean isRelativ;//whether or not fully relativistic
	public ArrayList<Element> elemListAll;
	
	public InputAgentGeo() {
		super(ProgramName.PW);
		//cell
		ibrav=new WrapperInteger(null);//no default
		unitCellLength=EnumUnitCellLength.angstrom;
		unitCellAngle=EnumUnitCellAngle.degree;
		cellA=new WrapperDouble(null);cellB=new WrapperDouble(null);cellC=new WrapperDouble(null);
		cellAngleAB=new WrapperDouble(null);cellAngleBC=new WrapperDouble(null);cellAngleAC=new WrapperDouble(null);
		unitCellParameter=EnumUnitCellParameter.angstrom;
		vectorA1=new WrapperDouble(null);vectorA2=new WrapperDouble(null);vectorA3=new WrapperDouble(null);
		vectorB1=new WrapperDouble(null);vectorB2=new WrapperDouble(null);vectorB3=new WrapperDouble(null);
		vectorC1=new WrapperDouble(null);vectorC2=new WrapperDouble(null);vectorC3=new WrapperDouble(null);
		//atom
		unitLength=EnumUnitAtomPos.alat;
		atomList=new ArrayList<Atom>();//for geoAtoms
		//elements
		typeFunctional=EnumFunctional.PBE;
		typePP=EnumPP.PAW;
		isRelativ=new WrapperBoolean(false);
		elemListAll = new ArrayList<Element>();//for geoElements,scfMagnet
	}
	public void updateElemListAll() {
		for (Atom tmp_atom : atomList) {
			if(!elemListAllContains(tmp_atom.getAtomSpecies())) {
				elemListAll.add(new Element(tmp_atom.getAtomSpecies()));
			}
			
		}
	}
	private Boolean elemListAllContains(ChemicalElements species) {
		for (Element tmp_elem : elemListAll) {
			if(tmp_elem.getAtomSpecies().toString().equals(species.toString())) {return true;}
		}
		return false;
	}
	public ArrayList<String> getElementStringList() {
		ArrayList<String> elem = new ArrayList<String>();
		for (Atom tmp : atomList) {
			if(!elem.contains(tmp.getAtomSpecies().toString())) {
				elem.add(tmp.getAtomSpecies().toString());
			}
		}
		return elem;
	}
}
